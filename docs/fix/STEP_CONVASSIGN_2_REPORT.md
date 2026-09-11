# STEP CONVASSIGN 2 REPORT: the assignment

The second of four commits in the operator-approved convention assignment build. Builds
the comparison itself: per-agent subject declarations, the routing function, its wiring at
BOOT, the never-dropped surfacing on the bus and through a read route, and the console's
fourth visible state.

## What changed

**`config/agent_registry.json`**: every one of the 18 agents gains a `subjects` field.
Twelve carry a real subject (answer 9's names, singular canonical form):

| subject | agent(s) |
|---|---|
| `conformance` | PRACTICE_AUDITOR |
| `wording` | STYLE_GUARDIAN |
| `basis` | LEGAL_ANALYST |
| `facts` | FACT_CHECKER |
| `fidelity` | VERIFIER |
| `redaction` | REDACTOR |
| `editorial` | EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION, EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG |

Six carry an empty list and a `subjects_note` explaining why, per answer 5: PROCESSOR,
ARCHIVIST, INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER (no convention-review path
reaches them today, or AUDIT-ONLY with no downstream reader), and AMENDMENT_DRAFTER
(reads findings, not rules, and its model call is off by default). A subject nobody can
act on invites a rule tagged for silence; the empty list is the honest declaration.

Reconciliation worth recording: the design document's own twelve-subject table proposed
five further subjects (`extraction`, `intent`, `references`, `actors`, `amendment`) for
exactly these six agents. Answer 5 overrides that: those five names are simply not
declared by any agent under this build. They are not forbidden or reserved anywhere in
code (declaring one would be exactly the reserved-vocabulary-in-code mistake this project
already rules out); an operator who tags a rule `[extraction]` today gets an honest
`unassigned` status, visible on the bus and in the console, until an agent declares that
subject or the operator retags the rule. 18 agents, 6 with an empty list, 12 covering
7 real subject names (editorial covering 6 agents), confirmed by direct count.

**`scripts/convention_assignment.py`** (new module): `assign_conventions(conventions,
agents)`, the whole comparison in the design document's own pseudocode (any overlap,
exact token equality, no synonyms). Takes `agents` as the registry's own `"agents"`
sub-dict directly (the shape `pipeline.py` already threads as `resolved_agents`, no
wrapper to unwrap). Returns `by_rule` (per rule: subjects, matched agents,
`consumer_agents`, and `status` in `{untagged, assigned, assigned_no_consumer,
unassigned}`) and `by_agent` (per agent: matched rule ids).

**A design correction found by testing, not assumed from the doc.** `consumer_agent_names`
first counted only `PRACTICE_AUDITOR`/`STYLE_GUARDIAN` (answer 6's firing-gate scope),
which made a rule tagged `[redaction]` or `[editorial]` wrongly read
`assigned_no_consumer`, though REDACTOR and the editorial board both have real,
live rule-consuming paths today (the keyword sniff; escalation). Consumer status now
answers "can something act on this rule at all" (`PRACTICE_AUDITOR`, `STYLE_GUARDIAN`,
`REDACTOR`, the six `EDITOR_*` ranks), a wider question than answer 6's firing-gate
scope, which only decides phase 5.5 dispatch (commit 3). The two questions are kept
separate in the module: `CONVENTION_REVIEW_AGENT_NAMES` (the firing-gate set, unchanged,
ready for commit 3) versus `consumer_agent_names()` (the wider surfacing set).

`untagged_count`, `unassigned_summary` (status `unassigned` or `assigned_no_consumer`,
never dropped, per the design document's own requirement), `idle_agents_summary` (an
agent that declares a subject but matched nothing, the condition commit 3's firing gate
needs), and `write_assignment` (writes `<run>/audit/convention_assignment.json`, same
write idiom as `pairing_map.write_pairing_map`).

**`scripts/pipeline.py`**: the comparison runs once at BOOT, right after the convention
registry is parsed (`parse_conventions` / `write_registry`, unchanged) and before the
first phase call. `resolved_agents` may still be `None` on one path (cloud backend with
`--skip-model-check`); falls back to reading the tracked file directly, the same idiom
already used elsewhere in this function for the same reason. The assignment is written to
the run's own audit directory and logged (`convention_assignment rules=N untagged=N
unassigned=N`, beside the existing `convention_registry rules=N` line, per answer 1's
"printed at load"). Every unassigned or consumer-less rule is enriched with
`source_rule_id` (via the existing `finding_record.source_rule_id_for`) and a plain-English
`reason`, then posted to the bus as `CONVENTION_UNASSIGNED` (computed, python, one flat
item per rule, `doc_id: ""` since the assignment is document-independent) only when at
least one such rule exists, the same "post it, never swallow it, never post an empty
one" discipline as `AMENDMENT_REFUSED`.

**`scripts/server.py`**: `_load_agent_registry_agents()` (a new `SHIMMER_AGENT_REGISTRY`
override, same pattern as the existing `SHIMMER_CONVENTION_REGISTRY`), the module-level
`_convention_assignment_for_run` reader (reads `audit/convention_assignment.json`
directly, same pattern as `_pairing_map`; the assignment is written once and never
rewritten mid-run, so a live bus read would only re-derive facts a plain file read
already has), and `GET /runs/{run_id}/convention-assignment`, returning `by_rule`,
`by_agent`, and `idle_agents` (computed server-side against the live agent registry, so
the console needs no second registry fetch of its own).

**`scripts/ui/console.html`**: the fourth visible state. `conventionAssignmentHtml`
(unassigned/consumer-less rules) and `idleAgentsHtml` (idle agents), both following the
exact disappears-when-empty pattern of `amendmentRefusalsHtml`/`contractViolationsHtml`:
return `""` when there is nothing to say, otherwise `h2` + muted note + `ul`, Reviewer and
Developer wording chosen by `isHumanView()`. Wired into `loadFindings` with two new
holders and one fetch to the new route; `wireRuleLinks` called on the unassigned holder so
a rule id there is openable the same way it is everywhere else on the surface. Untagged
rules are never listed here: an untagged rule keeps today's routing unchanged, so it is
not a problem to surface, only a fact reported once in the BOOT log line.

## What I got wrong before landing this, traced honestly

`resolved_agents` in `pipeline.py` is always the registry's own `"agents"` sub-dict, never
a `{"agents": ...}` wrapper; my first draft of `assign_conventions` expected the wrapper
and would have needed an unnecessary unwrap at every real call site. Caught before
wiring, by reading the actual call site rather than assuming the shape from the design
document's pseudocode alone; the function's parameter is now named `agents` and takes
the sub-dict directly, matching what `pipeline.py` actually has in hand.

The consumer-scope correction above (REDACTOR and the editorial board wrongly read
`assigned_no_consumer`) was found by running the function against the real registry and
reading its output, not by re-reading the design document more carefully; the document
itself does not resolve this ambiguity (it lists REDACTOR and the editorial board as
having a live path in its own table, but answer 6 narrows a different, adjacent question,
and the module's first draft conflated the two).

## Proof against real data

Direct call against the real `config/agent_registry.json`: 18 agents load, 12 declare a
real subject, 6 declare empty + note, matching the design exactly. A live BOOT smoke test
(the real `TopOrchestrator.boot` path, `tools/run_local_demo.py`, killed immediately after
BOOT, no full pipeline run) against the staged `device_log_review` corpus wrote
`output/runs/<id>/audit/convention_assignment.json` with all 8 rules correctly `untagged`
(the shipped corpus carries no bracket tags yet, per commit 1's own report) and logged
`convention_assignment rules=8 untagged=8 unassigned=0`.

## Gate check 198

Four sites, each against real code: the pure comparison (five status outcomes, the
corrected consumer scope, `untagged_count`/`unassigned_summary`/`idle_agents_summary`);
the BOOT wiring confirmed present in `pipeline.py`'s own source (driving `main()` through
the gate would require a live model call, out of scope; the function it calls is proven
live at the next site instead); the route through the real FastAPI app against a fixture
run directory (the correct `_RUN_ID_RE` shape, a 404 for a well-formed but unknown run,
neutralise-and-restore on the assignment file itself); the console's fourth state
confirmed present in `console.html`'s own source (both render functions, both holders,
the fetch call).

## Gate result

`PASS=197 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=199`, up from commit 1's `PASS=196 TOTAL=198`
by exactly one check (198), zero regressions. A real regression was caught and fixed
mid-commit: check 116 (README env table) failed once `SHIMMER_AGENT_REGISTRY` existed in
code with no README row; the row was added, the gate returned to only the two
pre-existing failures: check 01 (`missing dirs: ['prompts', 'snapshots']`) and check 145
(`tests/fixtures/planted_figure_hashes.json is missing`).

## README

Section E (conventions): unchanged from commit 1 (the assignment is a comparison over
what the parser already produces, not a further parsing change). Route table: the new
`/runs/{run_id}/convention-assignment` row. Env table: the new `SHIMMER_AGENT_REGISTRY`
row.

## What this does not do

No shipped corpus's `.md` file was edited to add a bracket subject tag (still true after
this commit; commit 1's report already noted this). Nothing in phase 5.5 reads the
assignment yet; no agent is skipped, no paired-mode dispatch changes. That is commit 3
(W3), which this commit's `idle_agents_summary` and `CONVENTION_REVIEW_AGENT_NAMES` are
built to feed directly.

## Things found on the way, not fixed here (per the operator's own instruction)

Unchanged from commit 1, recorded again, not touched: two em dashes in
`config/agent_registry.json:127` (still present in the file after this commit's edits,
which touched only the `subjects`/`subjects_note`/`note` fields around it); the missing
`previous_domain` vocabulary family; the unkept genesis Section C promise of a category
filter for STYLE_GUARDIAN.

---

STEP CONVASSIGN 2 COMPLETE (the comparison, its BOOT wiring, the never-dropped surfacing
on the bus and through a route, the console's fourth visible state; gate check 198;
README current; proven against real data through a live BOOT smoke test)
