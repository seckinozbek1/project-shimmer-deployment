# The execution pass after ordinary final run v7

Status: **CORRECTIONS_PROVEN_LOCALLY**. Local only: no cloud, no model execution, no weight
loading. Seven items were put on the table; two were defects and are corrected, five were not
defects and are reported with the evidence that decides each. No weights, HPO settings,
telemetry architecture, workload or routing changed. The one behaviour change is in phase 6 and
is stated under item 2.

## 1. Convention assignment is not the quality ceiling

**What `untagged` means.** `scripts/convention_assignment.py` compares each rule's subject tags
against each agent's declared subjects. The clinical conventions carry no subject tag at all
(their headings carry `[required]`, a severity), so all five are `untagged`. That status does
NOT withhold a rule. `convention_assignment.firing_convention_review_agents` (line 151) fires an
agent if it has an assigned rule **or** any loaded rule is untagged, "since an untagged rule
keeps today's default routing". The v7 evidence agrees: PRACTICE_AUDITOR was dispatched five
times, and `pairing_map` paired CONV-001 and CONV-002 across the units. Assignment is working as
designed and is not why anything is missed.

**Why RES-FIRTH's CONV-L02 defect is missed.** From the v7 pairing map, verbatim:

```
unit u06-result-res-firth | fields_present: [analysing laboratory, measured value, test]
  rejected: [{"rule_id": "CONV-002", "reason": "unit lacks sample identifier", "missing_count": 1}]
```

The pairing map rejects the completeness rule on the one unit that violates it, for the precise
reason that it violates it. A rule is paired to a unit when the unit carries every field the
rule names, so a rule about a field's absence is unpairable exactly where the field is absent.
`pairing_map.unmatched_findings` exists for this and raises a `missing_field` finding against the
nearest miss, but it is guarded by `if entry["paired"] or entry.get("undecided"): continue`, and
RES-FIRTH has both (CONV-001 paired, three rules undecided). So the safety net is switched off
by the unit being partly reviewable.

This is a real defect, and it is NOT corrected here. The fix is either a declared `requires:`
on the rule (which routes absence to Python through the existing `absence_path: computed` path,
and is the operator's file to edit, not mine) or a change to the pairing rule itself so that a
rule naming a field a unit lacks pairs as an absence question rather than being rejected. The
second touches the pairing contract, which is outside what this pass is allowed to change, and
the first is an operator decision about their own conventions. Both are stated for you rather
than chosen by me.

**Why the sheet count defect is missed.** `pairing_map.split_units` produces six units, one per
`## Result` heading. The header block carrying "Total result count declared: 6 / Northgate 4 /
Eastfield 3" sits above the first heading and is in no unit at all; measured directly, the string
is present in zero of six units. The scorer says the same thing independently:
`EVIDENCE_ABSENT_FROM_CORPUS, no unit of the parsed document contains 'sheet'`. The answer key
itself anticipated this: "The sheet-level count defect lives in the header block above the first
heading, which the unit splitter may or may not treat as a unit; it is planted honestly and
scored honestly either way." Correcting it means changing how documents are split into units,
which changes every unit id in every corpus and every saved pairing map. That is far larger than
this pass and is not done here.

Neither miss has anything to do with assignment. Both have a single named cause, and both causes
are structural decisions rather than bugs in the sense of a wrong line.

## 2. The promotion path, corrected at the call site

**What was wrong.** `pipeline.py:3096` states: "NO amendment is ever taken from the model ... an
amendment the arithmetic did not produce cannot exist by construction." `upstream_findings` at
3084 passed VERIFIER, FACT_CHECKER and LEGAL_ANALYST items into
`ensure_amendments_for_findings` alongside the computed ones. The invariant held only because no
model-authored record had ever carried `record_verdict: irregular`. In v7 VERIFIER ran with a
draft for the first time and wrote five such records, four with `value_a` equal to `value_b`.
Three were suppressed because a computed amendment already held their `(unit, rule)` key; the
two that did not, RES-CEDAR and RES-FIRTH, became operator-facing amendments. Both carried
`derived_from: "computed_finding"` and the sentence "Computed in code from the figures in this
unit, not judged by a model", which was false of both and also routed them past
`suppress_contradicted_amendments`, whose exemption at line 2391 skips that stamp.

**What changed.**

- `paired_review.computed_finding_items` selects the items of results Python computed, by the
  structural marker already written at the post: `backend "paired"` with a `model` beginning
  `python`. No agent name is read; PRACTICE_AUDITOR's judged-absence items are posted under the
  model's own backend on purpose and are model answers whoever wrote them.
- `pipeline.py` passes only those to the promoter. Every other channel is untouched:
  model-authored findings stay on the bus, in `apply_typed_fields`, in the deliverable's finding
  list, in the summary and in the ontology capture. Findings withheld from promotion are logged
  as `model_findings_not_promoted` with their agents.
- `amendment_from_finding` and `ensure_amendments_for_findings` take `computed_provenance`
  (default True, so every other caller is unchanged). With it False the stamp is `model_finding`
  and the sentence says "Reported by the agent named above, not computed in code from this
  unit's figures."

The docstring case is preserved: the function still exists to rescue arithmetic-backed findings
lost to a rule-id naming mismatch, and the three computed amendments are built exactly as before.

**Measured on v7's own recorded data.** The selector returns the three PRACTICE_AUDITOR units
and excludes all five VERIFIER records. Promotion over the narrowed input yields three
amendments; over the pre-correction input it yields five, the extra two being precisely
RES-CEDAR and RES-FIRTH.

## 3. The arithmetic guard would NOT have caught them

Run locally against v7's saved document, its compiled conventions and the two shipped
amendments:

| Input | Kept | Refused |
|---|---|---|
| As shipped, `derived_from: computed_finding` | 2 | 0 |
| With the corrected stamp, `derived_from: model_finding` | 2 | 0 |

The reason, measured: for both units `compute_checks` returns zero checks for the band rule, so
`relevant` is empty and the function takes its `arithmetic has no opinion on this rule` branch.
It abstains correctly rather than failing. This is the most important negative result of the
pass: correcting the stamp is necessary for honest provenance but would not have prevented the
false positive. Narrowing the promoter's input is the load-bearing correction, and the proof
asserts this outcome so the point cannot be lost.

## 4. The answer key, enriched, and all three runs re-scored

Each planted entry now carries a typed `claim` (relation, field_label, and the two figures where
the defect is arithmetic), read from the document and Section One of the reference corpus. No
planted entry, unit, rule or clean list changed, so every location-only figure already scored is
unchanged and only the reason check becomes answerable. No run evidence was touched.

| Run | Amendments | Recall, location only | Recall, reason confirmed | Right place wrong reason | False positives | Distractor hits |
|---|---|---|---|---|---|---|
| v5 | 3 | 3/5 | **3/5** | 0 | 0 | 0 |
| v6 | 3 | 3/5 | **3/5** | 0 | 0 | 0 |
| v7 | 5 | 3/5 | **3/5** | 0 | 1 | 1 |

All three location matches survive as confirmed detections in every run: ALDER 148 against 145,
BIRCH 3.1 against 3.5, ELDER 24 against 17, each with the right relation and field label. The
computed band findings are genuinely correct, not coincidences. Quality has been flat at 3/5
across three runs and roughly $3.50 of compute, and v7's two extra amendments were the false
positive and the wrong-reason one this pass removes.

## 5. Audit synthesis reporting zero is correct

`AuditSynthesizer.synthesize` is a cross-run PATTERN detector, not a findings report. Every one
of its five emitters has a threshold: three or more DISPUTED from one source, two or more
repeated anti-patterns, three or more escalations on a topic, two or more repeated charters, two
or more high-severity OMISSIONs. A single-document run with three band findings, no escalations
and no disputes trips none of them, so zero findings and zero DELTA proposals is the correct
output. The `stats` block in the same summary carries the real per-agent counts. Not a defect;
nothing corrected.

## 6. The grounding summary count is accurate

The sentence is "This document was reviewed against 5 conventions. 3 findings were produced by
PRACTICE_AUDITOR and STYLE_GUARDIAN." Its variable is built at `pipeline.py:3003-3016` from
exactly those two agents. In v7 PRACTICE_AUDITOR posted 3 items and STYLE_GUARDIAN 0, so 3 is
correct for what the sentence says it counts. It is not an amendment count and does not claim to
be. The apparent staleness against the deliverable's five amendments was caused by the promotion
defect putting two non-convention-review amendments into the deliverable; with item 2 corrected
the two numbers agree again for the right reason. Not a defect; nothing corrected.

## 7. STYLE_GUARDIAN and the absence forecast

**STYLE_GUARDIAN.** In paired mode the judging agent is `CONVENTION_REVIEW_AGENTS[0]`, which is
PRACTICE_AUDITOR, so STYLE_GUARDIAN never judges a pair. The activation ledger records this as
`different_assigned_plan_consumer` once per pair, eleven times per run. This is the documented
design, stated in `CONVENTION_ASSIGNMENT_DESIGN.md`: "the judging agent is pinned to
CONVENTION_REVIEW_AGENTS[0], so STYLE_GUARDIAN never runs in paired mode." Intended behaviour,
correctly recorded. Not a defect.

**The absence forecast.** `absence_quote_prediction.json` carries its own limit clause:
"Historical plan counts are a forecast, not a required cohort size or a claim count. Matching
counts do not establish identical documents." All three runs record `not_exercised` with zero
judged plans, which follows from the clinical rules declaring no `requires:` and no `scope:`, so
no absence plan is ever built. The artifact reports `count_comparison: differs` rather than
claiming a match. Behaving exactly as designed on a corpus that produces no absence plans. Not a
defect.

## Proofs

Check 269 and three executed proofs in `scripts/ordinary_final_correction_checks.py`, with two
neutralize/fail/restore/pass entries in the integration gate:

| Proof | Neutralised mechanism |
|---|---|
| only computed findings reach the promoter, over v7's recorded bus data | `computed_finding_items` returning every result's items, the pre-correction input |
| the stamp and sentence follow the source | `amendment_from_finding` ignoring the flag, the unconditional v7 stamp |
| v7's two shipped amendments are reproduced and the guard still abstains on them | (assertion-only; it records the negative result) |

## Gates

| Gate | Result |
|---|---|
| Correction checks | 22 checks, no skips |
| Compact-contract gate with its safe-gate baseline | 85 passed, PASS |
| Report-recommendations mutations | 15 of 15 |
| Controller, startup, decoding (CUDA) | PASS |
| Integration gate | 136 tests, 28 neutralize/fail/restore/pass proofs, PASS |
| Main gate against the clean baseline | see `docs/fix/ordinary_final_v8_gates/main_gate_comparison.json` |

Both pinned reference contracts carry a third amendment recording the `phase_6_synthesis` change.
