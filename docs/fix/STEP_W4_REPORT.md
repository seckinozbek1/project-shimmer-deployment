# STEP W4 REPORT: the harness

## What was built

`scripts/build_agent_harness.py`, run once, writes `config/agent_harness.json`: the nine-part
harness specification (the operator's own definition) for all 18 registry agents. It is
generated, not hand-authored, from `config/agent_registry.json` and
`config/agent_contracts.json` directly, so it cannot silently drift from the source it
describes. Re-running the script regenerates the same file from the same inputs; nothing in it
is invented.

## The nine parts, traced against real code, not assumed

**Part 1, the agent itself.** Read directly from `config/agent_registry.json`: `does`,
`does_not`, `category`, `backend`, `model`, `may_use_web`, `may_handle_sensitive`, per agent.

**Part 2, the constitution carried by default.** Decided, identically, for all 18 agents:
`scripts/agent_wrapper.py`'s `AgentWrapper.run_task` opens with
`situation = {"agent": self.name, "action": "execute_task", "tags": [...]}; check =
self.check_constitution(situation)`, unconditionally, every call, before anything
agent-specific happens.

**Part 3, the rule cluster assigned to it.** UNRESOLVED for every agent, and stays unresolved
here rather than invented. W2 (`docs/fix/STEP_W2_REPORT.md`) stopped at its own premise check:
no agent contract declares a subject/scope field, and the one structured field each side does
carry (agent `category` in the registry, convention `category` from `convention_parser.py`)
are two disjoint vocabularies built for different purposes, not one shared one. Every agent
still receives the full, unclustered convention registry today.

**Part 4, testing against that cluster.** UNRESOLVED for the same reason as part 3: there is
no cluster to test against.

**Part 5, ontological knowledge drawn in as required.** UNRESOLVED, by this step's own
instruction: the ontology work is W7, not yet run when this harness was built. Declared and
left unfilled rather than skipped.

**Part 6, the receive-format from other agents.** Decided, identically, for all 18 agents:
`scripts/bus_reader.py`'s `assemble_context(backend, constitution, bus, work_payload,
run_objectives="", charter=None, relevant_precedent_ids=None, channel=None,
recent_bus_limit=50, convention_registry=None, reference_index_excerpt=None)`, called from
`run_task` for every agent identically.

**Part 7, the hand-format to other agents.** Decided, identically: the INFRA-037 canonical
envelope, `{agent, doc_id, items[]}`, one flat item per output, every value a scalar or array
of scalars, posted to the append-only bus.

**Part 8, whether it fires at all.** Traced per agent GROUP against `scripts/pipeline.py`
directly; not one blanket answer. Four real shapes exist in this codebase today:

| Shape | Agents | Condition |
|---|---|---|
| Fixed per-phase list, unconditional | PROCESSOR, SPEECH_ACT_TAGGER, LEGAL_ANALYST, ARCHIVIST, INST_FINDER, CITATION_RESOLVER, VERIFIER, FACT_CHECKER, PRACTICE_AUDITOR, STYLE_GUARDIAN | Always fires, once per its fixed phase; no per-agent rule-cluster gate exists (part 3 is unresolved), so every agent in `PRODUCTION_AGENTS_PER_DOC` / `PRODUCTION_AGENTS_CORPUS_LEVEL` / `AUDIT_AGENTS_PER_DOC` / `CONVENTION_REVIEW_AGENTS` runs on every document. |
| Layer-gated | REDACTOR | Phase 9 (redaction) always RUNS as a phase, but REDACTOR's own call only posts bus messages while the sensitivity layer is active (`LAYER_ACTIVE` / `sensitivity_layer.is_active()`). Confirmed live: a completed run with `LAYER_ACTIVE` False produced zero REDACTOR bus messages (see `pipeline.py` line ~3536-3543, the note on run `cb4c557b`). |
| Bus-dedup-gated | AMENDMENT_DRAFTER | Skipped if a fresh payload already exists on the bus for that `doc_id` (`existing_amendments`); otherwise runs once per operational document. The model-call wording pass specifically is further gated by `--amendment-polish` (refine R2), off by default; the deterministic template path produces the amendment regardless. |
| Parsimony escalation | EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION, EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG | EDITOR_CLERK (entry rank) always fires once per deliverable. Each higher rank fires only when the rank below it triggers escalation: `_observation_triggers_escalation` (confidence below the operator's threshold, or, if enabled, an explicit `out_of_mandate` flag). Bounded by a terminal cap; most runs resolve at EDITOR_CLERK alone. |

**Part 9, how far it re-fires (retry condition and limit).** Decided, identically, for all 18
agents, and the decided answer is **zero**: `pipeline.py`'s `_run_one` calls
`wrapper.run_task` exactly once via `asyncio.to_thread`, no loop around the call anywhere in
the file; `agent_wrapper.py`'s `run_task` itself has no retry loop (the only backoff in the
module is a rate-limit retry inside `call_claude`/`call_gpt` for a 429/529 transport error, a
different thing from a contract violation). A `CONTRACT_VIOLATION` is posted to the bus and
the item is dropped (`_items_for` skips any result with `ok=False`); it is never
re-attempted. This is a real, confirmed fact in code, not a gap left unresolved: the code
decides it by having no retry mechanism at all.

## The gate check

Check 195 (`check_195_every_agent_has_a_nine_part_harness_and_unresolved_is_visible`), added to
`scripts/verify_session1.py`, proves exactly the property this step asked for: every one of
the 18 registry agents has a harness entry, every entry declares all nine parts, and an
unresolved part is visible AS unresolved (`"decided": false` plus a stated
`unresolved_because`), never simply absent from the file, which would look identical to a part
nobody thought of.

Neutralise and restore, inside the check itself: `PROCESSOR.rule_cluster.decided` is stripped
from a copy of the live file, the check is re-run against the mutated file and shown to FAIL,
then the original file is restored and the check is shown to PASS again. This proves the check
reads the live file's actual structure rather than a cached assumption about its shape.

## README

Added section "4a. The nine-part agent harness (`config/agent_harness.json`)" immediately
after the existing section 4 ("The single-agent harness", `scripts/harness/run_agent.py`),
naming both explicitly as two different senses of "harness" so a reader does not conflate the
debugging tool (one agent, one call) with this step's specification (what an agent is,
structurally, in nine parts).

## Gate result

`PASS=194 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=196`, up from the W0 baseline of `PASS=193
FAIL/ERROR=2 TOTAL=195` by exactly one check (195 itself), zero regressions. The two failures
are the same two pre-existing ones from every step of this chain so far: check 01 (`missing
dirs: ['prompts', 'snapshots']`) and check 145 (`tests/fixtures/planted_figure_hashes.json is
missing`), both environment artifacts absent from this checkout, neither touched by this step.

## What this means for the rest of the chain

W4 is not blocked by W2's stop the way W3 was: a harness with three parts marked unresolved
and six parts fully decided is a real, honest, buildable thing, per this step's own
instruction ("where a part is not decided, write it as unresolved and name it"). Nothing here
was invented to paper over W2's or W7's gaps.

---

STEP W4 COMPLETE (built: `config/agent_harness.json`, `scripts/build_agent_harness.py`, gate
check 195, README section 4a; three of nine parts correctly marked unresolved per W2/W7)
