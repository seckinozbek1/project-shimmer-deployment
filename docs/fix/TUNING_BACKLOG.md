# Tuning backlog

Work that needs a tuning cycle, recorded with the evidence that put it here. Nothing in this
file is authorized, started, or scheduled. An entry is a record, not a plan.

## FACT_CHECKER on the untuned Phi-3.5 base

**Status:** withheld for the `clinical_reference` review scope on 2026-09-19
(`config/review_scope.json`, `withheld_audit_agents`). Not removed from
`config/agent_registry.json` or from `AUDIT_AGENTS_PER_DOC`, so LAW-III enforcement is unchanged
and another corpus gets the agent back by clearing one declaration.

**What ruled it out.** Three instrumented cloud runs on this corpus, no substantively correct
item in any of them. The agent runs on the untuned `unsloth/Phi-3.5-mini-instruct-bnb-4bit`
base under the frozen greedy decoding policy.

| Run | Items | Contract | Substance |
|---|---|---|---|
| 110990c1 (v5) | 5 | passed (`verdict` present) | all 5 wrong: chloride 99 compared against sodium 148 across two different results; potassium 3.1 called ok when it is below the 3.5 bound; three comparisons against `null` |
| 6f896263 (v7) | 5 | failed, `verdict` absent on all 5 | all 5 wrong: `sum_mismatch` with 6 against 6; `missing_field` on complete entries; `product_mismatch` on in-range values |
| a6649672 (v8) | 5 | failed, `verdict` absent on all 5 | byte-identical to v7 (2,362 raw bytes), all 5 wrong, with a COMPLETE PROCESSOR draft available and consumed successfully by VERIFIER in the same phase |

**What was tried and did not move it.** Two prompt corrections, each measured: the typed-record
example rebuilt from the agent's own required list (v6), then the example filled with the
contract's declared values and the section naming the agent's own verdict-bearing field (v7).
v8's output is byte-identical to v7's, so the second correction changed nothing the model did.

**What the evidence does NOT establish.** Whether the failure is capability, prompt, or task
framing. Separating those needs model calls against controlled variants, which is a tuning
cycle. It is also not established that the agent fails on other corpora: every measurement here
is on `clinical_reference`, whose entries carry no explicit claim ids.

**The cheapest next measurement, if this is ever picked up.** One controlled A/B on the untuned
base, same document and policy, with and without the typed-record section, to establish whether
the section is what breaks the contract. That is a tuning-cycle question and is not authorized.

**Why withholding rather than deleting.** The agent's contract, registry entry and lane are
untouched, so nothing about the LAW-III split or the phase-5 shape changes structurally. The
declaration is data in the operator's own file, reversible in one line, and scoped to the corpus
where the evidence was gathered.
