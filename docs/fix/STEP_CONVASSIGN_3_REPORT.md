# STEP CONVASSIGN 3 REPORT: W3, unblocked

The third of four commits in the operator-approved convention assignment build. This is
W3 ("firing, and the fourth visible state") from the `/night` chain, which stopped at
`docs/fix/STEP_W3_REPORT.md` because "an agent with no conventions assigned" could not
occur before the assignment existed. It occurs now. The fourth visible state was already
built in commit 2 (the design document's own piece 2); this commit builds pieces 1 and 3:
the firing gate, and answer 7's larger change to how paired mode chooses its judging
agent, with the gate check piece 3 calls for.

This report does not edit `docs/fix/STEP_W3_REPORT.md`. That file is the accurate record
of what happened at that point in the chain, when the assignment genuinely did not exist;
this repository's own append-only discipline for governed history applies in spirit here
too. This report is the unblocked continuation, a new step, referencing the old one.

## What changed

**The firing gate (wide mode).** `_convention_review_firing_agents(convention_assignment)`,
a new pure function in `scripts/pipeline.py`: a convention-review agent
(`CONVENTION_REVIEW_AGENTS`, `PRACTICE_AUDITOR`/`STYLE_GUARDIAN`) fires if it has a real
assignment (`by_agent[name]` non-empty) OR at least one loaded rule is untagged. Wide
mode's dispatch loop (`phase_5_5_convention_review`) now builds a task only for
`firing_agents`, the filtered list, instead of iterating `CONVENTION_REVIEW_AGENTS`
directly; the result-zipping at the end of the loop follows the same filtered list.

**A correction traced from answer 1, not assumed from the design document.** The design
document's own piece 1 says "build a task only for an agent whose `by_agent` list is
non-empty." Read literally, that would silently stop BOTH `PRACTICE_AUDITOR` and
`STYLE_GUARDIAN` from firing on every shipped corpus today, since none carries a subject
tag yet (all `by_agent` lists are empty on an all-untagged corpus). That directly
contradicts answer 1's own instruction: "this changes nothing until I tag them." The
firing gate therefore treats an untagged rule as a reason to keep firing, not a reason to
stop; only when an agent has zero assigned rules AND zero untagged rules exist anywhere in
the loaded set does it have nothing to do. Confirmed with the operator before building,
since this reading genuinely contradicts the design document's own literal wording and the
contradiction needed resolving deliberately, not silently.

**The paired-mode judging agent (answer 7).** The design document's own text ("paired mode
receives the same `pairing` and `convention_registry`... `_paired_convention_review` still
pins `CONVENTION_REVIEW_AGENTS[0]`") was explicitly overridden: "The subject chooses the
judging agent. Do not filter the pairs to a fixed agent: that would silently stop wording
rules from being checked at all." `_paired_judging_agent(rule, convention_assignment)` is
a new pure function: the rule's own `consumer_agents` (already sorted, first wins) decides
who judges it; an untagged rule, or one whose consumer match is empty for any reason,
falls back to `PRACTICE_AUDITOR`, today's paired-mode default, unchanged until a rule is
tagged.

**The larger restructure this required, found by reading the real function, not assumed
from its signature.** `_paired_convention_review` used to build exactly ONE envelope and
post exactly ONE bus message for the whole document, under one fixed agent name. With the
judging agent now varying per plan, that single-envelope shape cannot hold: the function
now accumulates each agent's own findings separately
(`computed_items_by_agent: dict[agent] -> [items]`), then posts one envelope and one bus
message PER AGENT that actually judged something this document, returning one result dict
per agent (a shape `_items_for`, the INFRA-037 decoder, already handles correctly: its own
docstring already documents "an agent can now appear as MULTIPLE separate results for the
same doc_id," the D6 two-pass precedent; this is the same shape, one call site producing
several agent-attributed results, not a new consumer concern). `missing_field_findings`
(a unit the pairing map matched to nothing) is routed the same way, by its own
`rule_id`. A document with no plan and no missing-field finding at all still returns
exactly one empty-envelope result under the paired-mode default agent, matching the
pre-restructure shape for a zero-plan document.

## What I got wrong before landing this, traced honestly

My first draft of the check-198-adjacent gate proof used a single unit paired to both a
conformance-tagged and a wording-tagged rule, assuming both would produce a computed
disagreement. Running it live surfaced two real facts about `plan_calls` I had not
verified: rule-independent checks (sums, missing fields) are computed ONCE PER UNIT and
attributed to whichever rule names the involved fields, so a second rule on the same unit
with nothing further to compute produces no plan at all when the unit's shared checks
already cover everything; and an "uncomputable" plan (nothing Python could compute) still
triggers a real model call but `disagreements([])` on its empty checks list means it never
produces a Finding through this function, model judgment on an uncomputable pair is simply
not captured here today, a separate, pre-existing gap, out of scope for this commit.
Neither is a defect in this commit's own code; both are real properties of `plan_calls`
and `disagreements` that a synthetic fixture has to respect. Fixed by giving each rule its
own unit with its own independent computable arithmetic, so both genuinely produce a
Finding and both genuinely post to the bus under their own chosen agent.

A third error, found after the gate was green, while estimating the remaining work rather
than while building: `_paired_judging_agent`'s first draft took `consumer_agents[0]`
verbatim. Consumer status (commit 2) deliberately includes REDACTOR and the six editorial
ranks, since they read rules on their own paths (phase 9, phase 6.5). So a rule tagged
`[editorial]` would have dispatched a paired-mode call to EDITOR_CLERK, a rank that is
summoned by escalation and is never a judge in phase 5.5, and a rule tagged `[redaction]`
to REDACTOR. Neither fixture in check 199 could catch it, because both only used
PRACTICE_AUDITOR and STYLE_GUARDIAN. The function now takes the first consumer that is a
CONVENTION-REVIEW agent, and a rule whose consumers all sit outside phase 5.5 is judged
here by PRACTICE_AUDITOR exactly as every rule is today, never dispatched to another
phase's agent and never dropped from the review; those phases read the rule on their own
path regardless. Check 199 gained two assertions for exactly this: a board-only rule judged
by PRACTICE_AUDITOR, and a rule with a review consumer beside a board consumer judged by
the review consumer. The live smoke test that had been launched on the unfixed code was
killed and relaunched on the fixed code, so the proof below is of what was committed.

## A gate check fixed for a legitimate reason, not weakened

Check 157 (`wide mode intact; paired is the default only on the local profile`) text-
matched the literal string `for name in CONVENTION_REVIEW_AGENTS` inside phase 5.5's wide
branch, to prove the old dispatch loop still exists. The firing gate legitimately renamed
that loop to iterate `firing_agents`; the literal match broke, though wide mode's real
structure (task per firing agent, same `base_payload`, same `structural_inventory` branch)
is fully intact. Per CLAUDE.md's own rule ("do not weaken a gate check to make something
pass"), the check's text match was updated to the real current structure
(`for name in firing_agents`) AND strengthened with a further assertion that
`firing_agents` is genuinely derived from `CONVENTION_REVIEW_AGENTS` via the firing gate
(`firing_agents = _convention_review_firing_agents(convention_assignment)` must appear in
the branch) plus a direct call confirming `_convention_review_firing_agents(None)` returns
every agent, the rollback guarantee. This is fixing the check to match a legitimate rename
while proving strictly more than before, not loosening what it verifies.

## Live proof against real data

A live local paired-mode run against the staged, untagged `device_log_review` corpus
(the exact corpus commits 1 and 2 already smoke-tested), run `20260911T103414Z__de68946a`,
launched 10:34:14Z with `--pairs-per-unit 1 --max-docs 1`, both operator overrides and the
tier-1 manifest described below, on the committed code. What it proved, from its own log
(`output/w3_smoke.log` and `output/runs/20260911T103414Z__de68946a/`):

- BOOT, 10:34:18Z: `convention_assignment rules=8 untagged=8 unassigned=0`, and
  `audit/convention_assignment.json` written, every rule `untagged`: the
  no-assignment-tags-yet path, so the firing gate keeps both `PRACTICE_AUDITOR` and
  `STYLE_GUARDIAN` eligible and the paired judging agent falls back to `PRACTICE_AUDITOR`
  for every plan.
- Phase 3-4, 10:34:18Z to 10:58:25Z: six producer calls, 1447 s, no crash, no contract
  violation beyond the two pre-existing ones (CITATION_RESOLVER, SPEECH_ACT_TAGGER).
- Phase 5.5, 11:00:55Z: `paired_review pairs=19 dropped_by_cap=45 calls=19 saved=0`, the
  restructured `_paired_convention_review` entered with the assignment and produced the
  same pair count and call count as the pre-commit smoke test on this corpus.

The run was stopped by the operator's speed order while the 19 paired calls were still in
flight, before `paired_review_findings agent=` was logged, so the per-agent envelope post
is proven here by check 199 (which executes the real function with two senders) and not by
this run; with every rule untagged the run could only ever have shown `PRACTICE_AUDITOR`.
The whole run paced at ~230 s per producer call against 82 s for the same calls earlier in
the day, the paging finding recorded below.

## Gate check 199

Two sites. The firing gate: direct calls proving an agent with a real assignment but no
untagged fallback is excluded, and that `None` restores every agent (the exact
"rollback lever" check 157 also independently confirms). The paired-mode judging agent:
a live, executed (not read) call to the real `_paired_convention_review`, `_run_one`
stubbed so no model is called (the same pattern check 177 already established), with one
conformance-tagged and one wording-tagged rule, each independently computable on its own
unit in the same document. Confirmed: two separate bus posts, one under
`PRACTICE_AUDITOR` carrying CONV-001's finding, one under `STYLE_GUARDIAN` carrying
CONV-002's finding, the first time `STYLE_GUARDIAN` has ever fired in paired mode.
NEUTRALISE AND RESTORE: with `convention_assignment=None`, only `PRACTICE_AUDITOR` posts,
carrying BOTH findings (the pre-W3 shape), with the identical total finding count as the
tagged run, proving the restructure changes only attribution, never which findings exist
or get lost.

## Gate result

`PASS=198 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=200`, up from commit 2's `PASS=197 TOTAL=199`
by exactly one check (199), zero net regressions. A real regression was caught and fixed
mid-commit: check 157's literal text match broke on the legitimate loop-variable rename;
fixed by updating the check to the real structure and strengthening it, per the discussion
above. Same two pre-existing failures as every step before this one: check 01 (`missing
dirs: ['prompts', 'snapshots']`) and check 145 (`tests/fixtures/planted_figure_hashes.json
is missing`).

## README

No change in this commit: the firing gate and the paired-mode agent choice are dispatch
behavior, not a new surface, route, or environment variable; the route and console state
this behavior feeds were already documented in commit 2's report.

## What this does not do

No shipped corpus carries a subject tag, so no real run's routing changes yet: every
convention-review agent still fires on every document (the untagged fallback), and paired
mode still judges every pair as `PRACTICE_AUDITOR` (the no-real-assignment fallback),
exactly as before this commit, confirmed by the live smoke test. The firing gate and the
subject-chosen judging agent are real, live mechanisms now, proven by the gate and by a
real run, but they have nothing to act on differently until an operator writes a bracket
tag on a rule.

## Things found on the way, not fixed here (per the operator's own instruction)

Unchanged from commits 1 and 2, recorded again, not touched: two em dashes in
`config/agent_registry.json:127`; the missing `previous_domain` vocabulary family; the
unkept genesis Section C promise of a category filter for STYLE_GUARDIAN. One further
item found this commit, also left unfixed: an "uncomputable" paired-mode plan (nothing
Python could compute) triggers a real model call whose judgment is never captured into a
Finding by `_paired_convention_review`; `disagreements([])` on its empty checks list
means the call's own explanation is discarded. This predates this commit and is unrelated
to the firing gate or the judging-agent change; noted for a future step, not this one.

**The measurement corpus's membership in the review has been a web lookup.** Found when
the relaunched smoke test loaded zero operational documents with every file in place and
the cutoff untouched since September 3. Traced, not assumed: `device_log_flawed.md` has no
year in its filename; `document_dating._years_from_first_page` scans only the first 3000
characters (`text[:3000]`, line 204) and the log's first four-digit year sits at offset
4179, so the content pass has never dated it; there is no container metadata; the cascade
therefore falls to its last resort, `date_from_web`, a search-router query for the title's
publication date whose snippets are scanned for a year. Every run that has reviewed this
document so far (07:16, 09:30, 10:19 today) got its date, and so its operational status
under the 2025-06-01 cutoff, from that network lookup; at 10:30 the lookup returned
nothing and the same corpus reviewed nothing. The W6 measurement's own inclusion of the
document under review has rested on a web search, and would have silently reviewed
nothing on any day the search came back empty. Not fixed here: for the smoke test the
tier-1 operator manifest (`input/context/_review_targets.json`, a gitignored runtime
artifact written through `role_resolution.write_manifest`, naming the flawed log as the
target and the reference as grounding) states deterministically what the web lookup had
been supplying by luck; it is the mechanism the two negotiation corpora already ship with
and the device corpus does not. For the operator: the device corpora should carry that
manifest in `benchmark/corpora/*/context/` (or a dated filename), and `tools/stage_corpus.py`
should refuse to stage a corpus whose review target cannot be resolved without the
network, so a measurement can never depend on a search result.

**A local run needs ~12 GB of system memory, and this machine pages when it does not have
it.** Found because the smoke test's production calls ran at 227 to 229 s each against
82 s for the same calls this morning. Not the card: 61 C, no thermal or power-cap flag,
6.48 GB dedicated VRAM with no shared spill, idle between calls. The pipeline process had
committed ~12 GB of private memory against a 2.27 GB working set; the machine (15.7 GB)
showed ~2.5 GB available, 100k to 125k page faults per second, and bursts of 7,000 pages
per second read back from disk with the disk at 82 percent. The loader itself is not
holding a CPU copy of the weights (`agent_wrapper.py` loads with `device_map={"": 0}`,
which keeps the host footprint low, and its eviction path already collects host buffers);
the commit is the memory-mapped checkpoint files, the embedding model and store,
tokenizers and pinned CUDA host allocations together, and it is simply more than the
laptop has left with ~5 GB of other software open. Consequence for every estimate: a full
local run on this machine takes ~1 h with the memory free and ~3 h when it pages, which
is the difference between the W6 rerun being an afternoon and being a day. For the
operator: free ~3 GB before a measurement run (WSL's VM alone held 1.7 GB), or accept the
slower pace; neither is a code change.

---

STEP CONVASSIGN 3 COMPLETE (the firing gate; the subject-chosen paired judging agent,
answer 7's larger restructure; gate check 199; check 157 fixed for the legitimate rename;
proven live against the real, untagged, shipped corpus)
