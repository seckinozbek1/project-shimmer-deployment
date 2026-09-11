# STEP DIST A REPORT: the convention distribution reaches the paired path (and step B)

**These fixes are built without measurement. Each gap is real, because each was traced in
code. No fix is known to be correct until a run scores it. Nothing here is described as
working; the worst-case reading was taken in each design.**

## The gap, as traced

The pairing map (`pairing_map.build_pairing_map`) pairs rules with units from the registry
alone and never reads the convention assignment. `_paired_judging_agent` (commit 3) chose
the judging agent from the assignment but fell back to PRACTICE_AUDITOR for any rule whose
consumers held no convention-review agent. On the first tagged run (`d5728e4b`, stopped),
D06 to D08, assigned to the editorial board only, therefore still produced 51 of the 64
planned pairs and would all have been judged by PRACTICE_AUDITOR; wide mode showed every
rule to both convention-review agents through the full registry excerpt and the full
`evaluate_against` list. The operator's tags changed nothing in paired mode.

## What was built (step A)

- `_paired_judging_agent` returns `None` when an assignment was computed and the rule's row
  has a status other than `untagged` and no convention-review agent among its consumers
  (assigned to the board only, or matched by no agent). An untagged rule keeps
  PRACTICE_AUDITOR (answer 1). With no assignment (a caller that predates W3) every rule is
  judged as before. A rule id the assignment does not know keeps the default too, so a
  bookkeeping gap can never drop a rule.
- `_paired_convention_review`: a plan with no judging agent makes no call and is appended
  to `pairing["not_judged"]` (unit, rule, plan kind, the reason naming the consumers it was
  assigned to, the status); the map is rewritten with `not_judged`, `not_judged_count` and
  `reattributed`, and a `paired_review_not_judged count=N reattributed=M` line is logged. A
  `missing_field_findings` entry whose nearest-miss rule has no judging agent is recorded the
  same way rather than posted under a convention-review agent's name.
- Re-attribution: a rule-INDEPENDENT computed plan (a sum, a product, a missing field:
  `plan_calls` computes these once per unit and attributes them to one paired rule by field
  name) whose attributed rule has no judging agent is moved to another paired rule on the
  same unit that has one, preferring a rule naming the check's field, before it is judged;
  recorded under `reattributed`. A band plan or an uncomputable plan is rule-specific and is
  not moved. Worst-case reading taken: a computed finding is never posted under a board-only
  rule, and never invented for a rule the unit was not paired with.
- Wide mode: `_wide_registry_for_agent` gives each convention-review agent its assigned
  rules plus every untagged rule (plus any rule the assignment does not know), as both the
  registry excerpt `run_task` renders and the payload's `evaluate_against`; the rules no
  convention-review agent is shown are recorded in the map under `not_judged` with no unit
  (`_wide_not_judged`). The board's own reading in phase 6.5 is unchanged.
- `GET /runs/{run_id}/pairs` serves `not_judged` (with the operator's rule id) and
  `reattributed` beside the pairs, structural fields only.
- The harness builder's part 8 text for the convention-review agents no longer speaks of a
  PRACTICE_AUDITOR fallback; the harness file is regenerated.

## Step B: does paired mode need the firing gate?

No separate gate. In paired mode the judging agent is chosen per plan, so an agent with no
assigned rule and no untagged rule receives no plan and is never called; the wide-mode gate
(`_convention_review_firing_agents`) and the per-plan choice are the same rule read from the
same assignment. One thing did change: the empty result a document with nothing to judge
owes was always posted under `CONVENTION_REVIEW_AGENTS[0]`, which claimed PRACTICE_AUDITOR
had run even when the gate kept it from running. It now goes under the first agent the gate
lets fire, and when no agent fires the phase returns no result at all and logs
`paired_review_no_firing_agent`. Under the worst-case reading, a run whose every rule is
board-only produces no convention-review result in phase 5.5, which is the truth.

## Proof, on fixtures only

Check 206 executes the real `_paired_convention_review` (`_run_one` stubbed, no model) on a
three-unit document with two conformance rules and two board-only rules: no judging call
ever carries a board-only rule; the uncomputable board-only plan (Unit 9, CONV-005) is in
the saved map's `not_judged` with `EDITOR_CLERK` named as its consumer; Unit 8's computed
sum mismatch, which `_rule_for_check` attributed to the board-only CONV-002, is posted under
CONV-003 by PRACTICE_AUDITOR (re-attributed, recorded); the direct helper moves the plan to
CONV-003 and refuses to invent a rule the unit was not paired with; the wide excerpt for
PRACTICE_AUDITOR is its two rules plus the untagged one, STYLE_GUARDIAN's is the untagged one
alone, and with no assignment the whole registry is shown; the wide not-judged record lists
exactly the two board-only rules; the wide loop's source applies the per-agent excerpt. Step
B: a document whose only rule is board-only, under an assignment where no convention-review
agent fires, produces no call and no result.

Neutralised, with `_paired_judging_agent` replaced by commit 3's fallback (always
PRACTICE_AUDITOR):

```
('FAIL', "a board-only rule reached a judging call: [('PRACTICE_AUDITOR', 'u01-unit-7',
'CONV-001'), ('PRACTICE_AUDITOR', 'u02-unit-8', 'CONV-002'), ('PRACTICE_AUDITOR',
'u03-unit-9', 'CONV-005')]")
```

Restored: `PASS`. Check 199 was updated, not weakened: its board-only assertion now requires
`None` (no judging agent) instead of PRACTICE_AUDITOR, and gained the unassigned, untagged
and unknown-rule cases; its live two-agent proof is unchanged. Checks 157 and 177 pass
unchanged.

The fixture found a second instance of gap D on the way: a unit carrying only the label
"Total declared extent" was rejected by a rule whose text contains the word "extent",
because "extent" is also a table header in another unit and so a field the rule "names".
The fixture was rewritten around it; the gap is D's, recorded there, not fixed here.

## What a run will have to show

On the device corpus with the operator's tags, phase 5.5 should plan the same 64 pairs and
make calls for the D01 plans only (13 pairs, before Python's own computed findings), record
51 plans under `not_judged` naming the six editor ranks, and post nothing under D06 to D08.
Whether the review is better or worse for it is not known; that is what the run is for.

## Gate result

```
PASS=205  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=207
```

`output/dist_a_gate1.log`, run once at this HEAD. One check added (206), one more pass,
WARN 0, the same two source-only failures (checks 01 and 145).

---

STEP DIST A COMPLETE (built without measurement; proved on fixtures by check 206; step B
answered and its one change built)
