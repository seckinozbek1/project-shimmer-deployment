# Productization state at this HEAD

One honest picture of this repository for a reader who has not followed the work. Every
claim carries a citation to a file, a report or a commit in this repository. Nothing here is
a plan; it is what is true now.

**Written at the close of the night chain (W0 to W9) on branch `night-2026-09-11`, 2026-09-11,
at the HEAD that carries this document.** This is the first state document in this
repository: the private repository's own `docs/PRODUCTIZATION_STATE.md` was not part of the
public snapshot (`docs/publish/`), so nothing older is rewritten here; what an earlier state
document said about the private branch is not repeated as a claim about this one.

---

## 0. The night chain, step by step

The chain's instruction file was `.claude/commands/night.md` (local, never committed). The
operator stopped the chain at W6 on the morning of 2026-09-11 and re-ordered the rest; the
convention assignment (W2) moved to the front as a design document plus four commits, then
W3 inside them, then W7, W8, W9, with the W6 rerun waiting on an operator action. Every
step has a report under `docs/fix/` (gitignored; every one is added with `git add -f`).

| step | what | status | commit | report |
|---|---|---|---|---|
| W0 | stop the running review, harvest, merge `api`, `console`, `docker` into `main`, branch | COMPLETE; zero conflicts; `main` at `d007c27` | `d132af8` | `STEP_W0_REPORT.md` |
| W1 | the measurement corpus (`device_log_review`, flawed and clean twin; 19 units, 8 conventions) | COMPLETE | `2503b3b` | `STEP_W1_REPORT.md` |
| W2 | distribute conventions to agents | STOPPED at its own premise check; later built as the convention assignment (below) | `20c0a0d` | `STEP_W2_REPORT.md` |
| W3 | firing, and the fourth visible state | skipped in the chain (depended on W2); built as convention assignment commit 3 | `bcb10c5`, then `63d2774` | `STEP_W3_REPORT.md`, `STEP_CONVASSIGN_3_REPORT.md` |
| W4 | the nine-part agent harness | COMPLETE with three parts unresolved; two closed by commit 4, ontology still open | `c037e46`, then `4db14aa` | `STEP_W4_REPORT.md`, `STEP_CONVASSIGN_4_REPORT.md` |
| W5 | the three remaining rule-id name mismatches (plus a fourth found on the way) | COMPLETE | `d20e2c9` | `STEP_W5_REPORT.md` |
| W6 | measure | STOPPED by the operator; the measurement is still owed | `04962ce` | `STEP_W6_REPORT.md` |
| design | `docs/api/CONVENTION_ASSIGNMENT_DESIGN.md`, approved with ten answers | COMPLETE | `e15d9b3` | the document itself |
| CA1 | bracket tags, severity from the bracket, the preamble fix | COMPLETE | `bea4c96` | `STEP_CONVASSIGN_1_REPORT.md` |
| CA2 | the comparison, its route, the fourth console state | COMPLETE | `3bbe3ec` | `STEP_CONVASSIGN_2_REPORT.md` |
| CA3 (W3) | the firing gate and the subject-chosen paired agent | COMPLETE | `63d2774` | `STEP_CONVASSIGN_3_REPORT.md` |
| CA4 | harness parts 3, 4 and 8 regenerated; the gate's unresolved set is ontology only | COMPLETE | `4db14aa` | `STEP_CONVASSIGN_4_REPORT.md` |
| W7 | ontology foundations | COMPLETE: (b) to (e) built and gate-proved in `b31fbb9`; (a) archived and emptied by the operator at 12:15:43Z with the tool built there (archive `shimmer-archives/ontology_stores_20260911T121543Z.zip`, 13107 bytes) | `b31fbb9` | `STEP_W7_REPORT.md` |
| W8 | the console | COMPLETE, with screenshots | `ad495c2` | `STEP_W8_REPORT.md` |
| W9 | close (this document) | COMPLETE; written in `1acf6bd`, updated once after the operator's archive run | `1acf6bd` and the commit carrying this update | `STEP_W9_REPORT.md` |

Nothing was pushed by any step. `main` stays at the merged `d007c27`; all of the above is
on `night-2026-09-11`.

## 1. What changed, grouped by concern

### The convention assignment (the W2 decision, built)

A one-way subject label on each side, compared by code that knows no subject name
(`docs/api/CONVENTION_ASSIGNMENT_DESIGN.md`). Each agent declares the subjects it handles
in `config/agent_registry.json` (`subjects`; six agents declare an empty list with a
`subjects_note`). Each convention carries the subject its author chose, as bracket tags on
its heading, read structurally by `scripts/convention_parser.py` (`_heading_bracket_tags`;
the severity comes from the same bracket; prose before the first operator-id heading is no
longer minted as a rule). `scripts/convention_assignment.py` compares the two lists once, at
BOOT, by exact token overlap (`assign_conventions`), writes
`<run>/audit/convention_assignment.json`, and posts every rule that matched no agent with a
live path to the bus as `CONVENTION_UNASSIGNED`, never dropped. `GET
/runs/{run_id}/convention-assignment` serves it. An untagged rule keeps today's routing to
every convention-review agent and is counted at BOOT.

### The firing gate (W3)

In wide mode a convention-review agent fires only if the assignment gave it a rule or any
loaded rule is untagged (`convention_assignment.firing_convention_review_agents`, which
`pipeline._convention_review_firing_agents` delegates to). In paired mode the rule's own
subject chooses the judging agent (`pipeline._paired_judging_agent`, PRACTICE_AUDITOR as the
fallback), one envelope and one bus post per agent, so STYLE_GUARDIAN can produce typed
findings in paired mode for the first time (checks 157, 199).

### The harness (W4, corrected)

`config/agent_harness.json`, built by `scripts/build_agent_harness.py` from the registry and
the contracts: nine parts per agent. Parts 3 and 4 (the rule cluster and testing against
it) are decided by the assignment; part 8 carries the firing gate for the two
convention-review agents and the D6 two-pass shape for LEGAL_ANALYST; part 5, ontology, is
the one part still `decided: false` for every agent (check 195 requires exactly that, on a
tempdir copy, never writing the live file).

### The ontology foundations (W7)

`scripts/ontology_store.py`: a scope enforced on every read and write inside the storage
layer, defaulting to one value (`DEFAULT_SCOPE`) bound in pipeline phase 8; a provenance
struct `{time, agent, run, type}` on every provision record (type `document`; the
rule-derived type declared unfilled and refused until observed; no confidence field); a live
store and an immutable log (`provisions.jsonl`, `provisions_log.jsonl`) with supersession
decided at the query layer and compaction moving superseded revisions to the log; supersede
built, delete declared and refusing. Capture, graph and GNN read and write through it;
phase 6 stamps each Finding's agent so the amendment and the captured record can name it.
Checks 200 to 202. `tools/archive_ontology_stores.py` archives the stores as a dated zip
outside the repository and empties them.

### The console (W8)

On a run's page: the distribution (which rules each agent handles, the untagged count), the
rules no agent handles, the convention checkers the firing gate kept from running (fed by the
gate's own function), and the agents no tagged rule reached, worded as what is true. A third
tab, Agents, shows every agent's nine-part harness with undecided parts marked, via `GET
/harness` (`SHIMMER_AGENT_HARNESS`). Both views, wording apart. Proved on the stubbed server
through a headless browser (`tools/console_preview.py --screenshots`), six captures under
`docs/fix/w8_screenshots/`, and by check 203.

### The name mismatches (W5)

Every remaining consumer of a rule id reads through `finding_record.resolved_rule_id`; a
`KeyError` waiting behind one of them was fixed alongside (check 196).

### The gate itself

From PASS=193 TOTAL=195 at W0 (`STEP_W0_REPORT.md`) to PASS=202 TOTAL=204 at W8, WARN 0
throughout, the same two failures on every run of this snapshot: check 01 (missing
`prompts/` and `snapshots/`) and check 145 (missing `tests/fixtures/planted_figure_hashes.json`),
both properties of a source-only checkout, recorded in README section L. Checks added: 195
to 203. One check corrected for a legitimate reason each time (157's loop text, 143's
section window, 59 and 60's fixtures written through the store), none weakened.

## 2. What the measurement showed

W6 was run once on the flawed corpus and stopped by the operator during the paired phase
(`STEP_W6_REPORT.md`); the clean twin was never run. What that partial run established,
verbatim from its own artifacts:

- 86 model calls, all local: 73 of them the paired phase (one per pair, PRACTICE_AUDITOR
  only; STYLE_GUARDIAN's share not reached), 6 LEGAL_ANALYST (one pass-one call, then one
  per finding: D6), one each for the other producers.
- 101 pairs planned for 19 units and 10 registry rules: 57 by the similarity fallback (the
  rule names no field the document uses), 18 by a rule naming only the entry's identifier.
- Python computed nothing on this corpus: the reference states its class bands in prose, not
  in a table, so the arithmetic path was idle and every pair was a model call.
- Four contract violations, none retried, each a valid envelope inside a wrapper the parser
  refuses.
- Scorer result: recall 0 of 9 (0 of 3 in each of the three flaw kinds), false positives
  and distractor hits 0 of 0 amendments. This zero is void, not negative: the run was
  stopped before any deliverable and no finding carried a unit id, so nothing could match.
- Whether the neighbour mechanism catches the neighbour-dependent flaws: not determined.

The operator's call was that measuring the old shape at 101 pairs was not worth another
hour when the convention distribution would change the call count. The rerun on the tagged
corpus (`dccec5f`) was started on 2026-09-11 at 12:33Z and stopped by the operator at
13:19Z, again in the paired phase, again before any deliverable (`STEP_W6_REPORT.md`, the
second-stop section). What it established: the assignment is real (D01 to D05 on
PRACTICE_AUDITOR, D06 to D08 on the board, STYLE_GUARDIAN the first real not-firing entry);
64 pairs planned from 8 rules, the drop from 101 being the preamble fix and not the tags,
because the pairing map never reads the assignment; and D02 to D05, the four rules that
check the planted flaw kinds, paired with nothing, because the pairing map pairs a rule
only with a unit carrying every field the rule names, so an absence flaw hides the very
field the pairing needs. The neighbour question is still not determined. From that stop a
standing rule holds (`CLAUDE.md`): no pipeline run of any kind from this laptop, and none
asked for, until development moves to a rented GPU box; every proof on fixtures, mocks,
deterministic paths and saved artifacts. Two measurements from the smoke runs around the assignment commits are recorded in
`STEP_CONVASSIGN_3_REPORT.md`: the same corpus at `--pairs-per-unit 1` plans 19 pairs, and a
local run commits about 12 GB of private memory, so on this 15.7 GB machine with under
about 3 GB free every model call ran roughly 2.8 times slower (230 s against 82 s for the
same producer call). No number in this section came from a cloud model; S3 held throughout.

## 3. Unwired, undecided or found and not fixed at this HEAD

Each item is recorded in the report named; none was fixed by the chain, by the operator's
own instruction ("record them, do not fix them now") or because it lies outside a step's
written scope.

| item | where recorded | state |
|---|---|---|
| The ontology and GNN stores: archived outside the repository and emptied by the operator (the agent's own run of the tool was refused by its permission layer); `ontology/stores/` now holds an empty `provisions.jsonl` only | `STEP_W7_REPORT.md` a | closed |
| No engagement concept: the scope identifier has one value and no binding to a real client | `STEP_W7_REPORT.md` c | mechanism built, concept not |
| Deletion in the ontology store: declared, refuses | `STEP_W7_REPORT.md` e | operator decision not finalised |
| GNN learning, the candidate finder, the long-range mechanism, curation interfaces, developer defaults, the two rule sets, any convention hierarchy | `STEP_W7_REPORT.md` | not started, by instruction |
| The harness's ontology part stays `decided: false` for all 18 agents: W7 built the store, no agent reads it | `STEP_CONVASSIGN_4_REPORT.md`, `STEP_W8_REPORT.md` | open until an agent draws from the store |
| `ontology/SCHEMA.md`, cited by all three ontology modules as the ratified schema, does not exist in this repository | `STEP_W7_REPORT.md` | the code is the only specification |
| No shipped corpus carries a subject tag; every real run routes as before tagging existed | `STEP_CONVASSIGN_3_REPORT.md` | waits on the operator tagging rules |
| The device corpus's operational status rode on a web lookup (no filename year; the first year sits past the 3000-character scan); the smoke runs used a tier-1 manifest instead | `STEP_CONVASSIGN_3_REPORT.md` | not fixed; a measurement must never depend on a search result |
| A local run commits about 12 GB and this machine pages below about 3 GB free | `STEP_CONVASSIGN_3_REPORT.md` | not fixed; free memory before a measurement run or accept the pace |
| An uncomputable paired plan's model judgment is never captured into a Finding | `STEP_CONVASSIGN_3_REPORT.md` | not fixed |
| D6 pass two's deepened item reaches the bus at revision 1 under a fresh id; only the in-process result carries the supersession | `STEP_W6_REPORT.md` finding 2 | not fixed; a record living only in a return value is not a record |
| `unit_id` is never stamped by Python in paired mode though known by construction | `STEP_W6_REPORT.md` finding 4 | not fixed |
| Prose reference bands: nothing computable on the device corpus; the arithmetic path is idle there | `STEP_W6_REPORT.md` finding 6 | a corpus matter (write the bands as a table) |
| 57 of 101 pairs by similarity fallback; a rule naming only the identifier pairs with everything | `STEP_W6_REPORT.md` finding 7 | expected to change with tagged rules |
| Two em dashes in `config/agent_registry.json:144` (EDITOR_DG), copied into `config/agent_harness.json` | `STEP_CONVASSIGN_4_REPORT.md` | not fixed, by instruction |
| The `previous_domain` vocabulary family named in `CLAUDE.md` is missing from `config/domain_vocabulary.json` | `STEP_CONVASSIGN_1_REPORT.md` | not fixed, by instruction |
| genesis Section C's STYLE_GUARDIAN filter promise was never written | `STEP_CONVASSIGN_1_REPORT.md` | not fixed; genesis is governed (S8) |
| `tools/score_corpus.py` is covered by no gate check | `STEP_W6_REPORT.md` | its per-kind recall and partial-run scoring were dry-run only |
| The server's run-id shape (`\d{8}_\d{6}__[0-9a-f]{6}`) does not accept a CLI run's folder name (`20260911T103414Z__de68946a`) | check 198's fixture shape; `run_context` | carried over from before the chain; unchanged |
| The LAW-IV masking layer is built and inactive (`LAYER_ACTIVE = False`); every capture so far wrote real text | `scripts/sensitivity_layer/__init__.py:70`; README section F | an operator DELTA, unchanged |
| Checks 01 and 145 fail on this source-only snapshot | README section L | by design |

## 4. Every open decision that belongs to the operator

| decision | what depends on it |
|---|---|
| **Tag the eight device rules** (`benchmark/corpora/device_log_review/.../device_conventions.md`, bracket subject tags on the headings, from the subjects the registry declares) | The W6 rerun on the new call count, both runs, scored. Nothing else in the chain is blocked on it; the tagging is the operator's knowledge and is not to be invented by an agent |
| **Free about 3 GB before a measurement run, or accept the paged pace** | Wall clock of the W6 rerun: about 1 h per run with memory free, about 3 h paging, plus the driver-fault allowance |
| **The machine for measurement, bursty and not always on** (the operator's own words) | A one-off estimate stands, no VM rented: one A100 80 GB class VM on demand (about $1.8 per hour on a GPU cloud, $26 to $28 on a hyperscaler for the whole effort) covers a pipeline run or the gate, both of which need CUDA (check 193 loads a local model); one A10G is about $6 to $8 for the same; a cloud API profile for runs is excluded by S3 and would change the measurement baseline. The build and report work does not shrink with GPU; only the runs and gates do |
| **The user-facing deletion case in the ontology store** | `ProvisionStore.delete` (declared, refuses) and the logging of a deletion |
| **What the engagement identifier is and where it is bound** | The scope's one value becomes many; the binding point is pipeline phase 8 |
| **Activate the LAW-IV masking layer** (`LAYER_ACTIVE = True`) | Every sensitive run; the ontology stores' masked-write gate keys on it |
| **Ship the device corpus's review-targets manifest, or make `tools/stage_corpus.py` refuse a target whose date depends on a network lookup** | Whether a measurement can ever silently review nothing |
| **Whether the harness's ontology part should be marked decided as "draws nothing today"** | Check 195's unresolved set; the Agents page's undecided marker. Left undecided because an agent that reads the store does not yet exist |
| **Push** | Nothing has been pushed from this clone by any step. The push target guard stands |

## 4a. After the close: the fixes built without measurement (2026-09-11, afternoon)

Added after the second W6 stop, under the standing rule (no pipeline run from this
machine). Each was traced in code, proved on fixtures by a gate check with neutralise, fail,
restore, pass, and committed on its own; none is known to be correct until a run on the VM
scores it. Every report under `docs/fix/` says so.

| commit | what | check |
|---|---|---|
| `bb39bdd` | W6 stopped a second time; the standing no-runs rule in `CLAUDE.md` | |
| `0daeb26` | call evidence recorded per model call (structural ids only) and the four-class false-negative classifier through the scorer | 204, 205 |
| `e385ed6` | convention distribution reaches the paired path: board-only rules never judged, recorded; wide excerpt filtered; paired-mode firing (step B) | 206, 199 updated |
| `33803de` | the three recording gaps closed: rendered ids read off the finished sections, the draft call, the probe | 207 |
| `3733565` | longest-match labels in the pairing map (D, option 1) | 208 |
| `cc20ffd` | declared scope and Python-first absence (D, option 2): `[scope: ...]`, `[requires: ...]`, computed and judged paths recorded | 209 |
| `a3c666f` | the container: entrypoint line endings, `accelerate` pinned, check 197 freed of the corpus file; the first offline gate inside the image | 197 updated |
| the declarations commit | the four device declarations on the operator's corrected wording, applied to both twins after a deterministic probe of the first draft (`STEP_DECL_REPORT.md`): D02 `[scope: class=Class-A sensor] [requires: calibration authority signature]`, D03 `[scope: calibration authority signature]`, D04 `[scope: fault logged]`, D05 `[scope: service record]` | 197 still passes |
| the commit carrying this line | the README audited start to finish against HEAD (65 findings, `STEP_README_REPORT.md`); the Dockerfile's weight layers moved before the source layers; the baked image built here with the three checkpoints inside and its offline gate run with no cache mounted (`STEP_BAKED_REPORT.md`) | none added |

The container's offline gate, network blocked, host cache mounted: PASS=204 SKIP=2
FAIL/ERROR=4 of 210, the four failures the documented source-only ones; inside the baked
image with nothing mounted, the same line in about 510 s. The first draft of the device
declarations had one scope value (`class=A`) that never matches what the parser reads off
the entries (the value test is equality on `class-a sensor`) and two declarations that
turned a window rule into a presence rule never reaching the model (51 computed absences on
both corpora, the one entry each rule is about left unasked); the operator corrected all
three, and the applied form plans 37 calls on the flawed log and 43 on the clean twin (34
and 46 with no declaration), D04 and D05 each reaching the model once on the entry they are
about. The W6 measurement is still owed.

## 5. Before this branch merges into `main`, in order

1. The W6 rerun is made on a machine with a free GPU (flawed and clean twin, scored by
   `tools/score_corpus.py`; the eight subject tags and the four declarations are applied,
   `dccec5f` and the declarations commit); the numbers go into `STEP_W6_REPORT.md`'s owed
   section and replace section 2 above.
2. The gate once more on a clean clone with a fresh `.venv` from the pinned
   `requirements.txt`; expect exactly the four source-only failures (01, 28, 31, 145;
   README section L), since a clean clone has no `input/` at all.
3. An independent read-only audit at the merge HEAD: this chain wrote its own checks (195
   to 203), and a check that passes for the wrong reason is caught only by a reader who did
   not write it. An adversarial review before commit 4 found four real defects in that
   commit's prose and one check; that is the argument for doing it again at the end.
4. Merge, and push only on the operator's word.

(The archive-and-empty that stood here as step 2 was done by the operator at 12:15:43Z on
2026-09-11, after `b31fbb9`; see the W7 report.)
