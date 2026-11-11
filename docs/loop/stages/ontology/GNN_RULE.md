# The GNN's rule, and the ontology's life cycle (D-S112 item 1, D-S114; D-413, D-417, D-418, D-419)

Written 9 November 2026 on lane/gnn-rule. Nothing below has run.

The rule, from Seckin, applied as decided:
- **D-S112 item 1:** the GNN does not learn from runs by itself. It has its own training, domain- and
  case-agnostic, separate from any use. After deployment it is trained further on a user's material
  only if that user asks for it ("improve accuracy with the GNN").
- **D-S114 item 1, corrected:** the GNN is the ontology's training mechanism. The first ontology, the
  agnostic base, is produced by a GNN training now. Later updates happen only when asked, never
  automatically between runs.
- **D-419:** an update runs by its own command, on declared material, only when asked, never
  triggered by runs. A calibrated trigger or minimum is a proposal shown to the person who asks,
  never an automatic start.

## 1. What changed in code (D-417, commit f0cbbd8e, rows 1 to 4, 10 and 11 of D-413's table)

- No run trains the GNN: the pipeline's run end no longer calls `ontology_gnn.gnn_update` and no
  longer imports `ontology_gnn`. Capture and the graph rebuild are unchanged; their lock is D-S61's,
  on lane/ontology.
- `gnn_update(training_set, state_path)` trains only on a declared training set
  (`declare_training_set`: kind `gnn-training-set-v1`, one graph file by path and SHA-256, stated
  domain- and case-agnostic, made for training). Before any weight moves, it refuses:
  - the run-captured store;
  - an undeclared training set, or one not stated agnostic;
  - a set whose graph changed since it was declared;
  - a missing state path.
  Its only command is `scripts/ontology_gnn.py train --training-set <file> --state <file>`.
- Gate check 64 is inverted: no run path calls `gnn_update` (an AST scan of `scripts/` and
  `tools/`). Its proofs and neutralisations are in `scripts/ontology_gnn_rule_checks.py`. Checks 62,
  63 and 213 run on declared sets.
- Kept on purpose: within its own training, `gnn_update` still keeps its high-water mark, so a second
  call on the same declared graph trains nothing new. Row 4 had proposed dropping it. It is kept
  because check 213 proves the weights persist rather than reset, and with no run calling it the
  mark no longer tracks runs.
- CLAUDE.md (the `ontology/stores/` paragraph) and `docs/RUNTIME_REFERENCE.md` say so.

### 1a. After gnn-rule-check (D-432 items 1 to 5)

- **The run-trained state is archived.** The main checkout's `ontology/stores/gnn_state.json`
  (sha256 98cc4c75...f000, 27,422 bytes, trained at runs' ends before D-417) is archived out of the
  stores with `tools/archive_ontology_stores.py --only gnn_state.json --reason ...`. The archive is
  `ontology_gnn_state_json_20261109T183710Z.zip` in the shimmer-archives folder beside the
  repository, its record beside it as `.record.json`. No other worktree held one.
- **Every reader refuses a state without its chain.** A state names its whole chain of training sets
  (`training_sets`: name, graph digest, declaring person, in order). One without the chain is
  refused by `ontology_gnn_state.state_summary` (`usable: false` with the reason), by the candidate
  finder (`StateRefused`; `/ontology/candidates` answers 409) and by the training command.
- **The run store is refused by content.** The checks are the place, the graph's bytes against every
  file of `ontology/stores/`, and the build provenance `ontology_graph` now writes (`built_from`:
  which sources were the repository's own stores).
- **The agnostic statement is the declaring person's.** It is made by
  `ontology_gnn.py declare --domain-agnostic --case-agnostic --declared-by <name>`, never defaulted
  by the tool, and is recorded with that name. Stated limit (`AGNOSTIC_LIMIT`): the tool checks the
  form, the digest and that the graph is not the run store's, not the material itself. A graph
  copied from the store and then edited, or built from it by other code, is not caught.
- **Check 64's scan, with its scope stated.** It reads every Python file of `scripts/`, `tools/`,
  `benchmark/` and `corpus_ingest/`, the launchers and the container files. In Python it catches:
  - a call of `gnn_update` by its name or an alias;
  - `ontology_gnn.gnn_update` or `ontology_gnn.main` taken from the module under any alias
    (including `importlib.import_module` and `__import__`);
  - `getattr` of either;
  - any string naming the training command.

  In the other files it catches any line naming `ontology_gnn`. A name built at run time is not
  caught.
- **Every refusal has its proof.** No declaration, wrong kind, not domain-agnostic, not
  case-agnostic, no name, no material, no declaring person, no state path, a statement not made by
  the person, a changed graph: each is refused and each refusal is neutralised in turn.
- **Check 64 runs the pipeline's own run end.** The block moved into `pipeline._ontology_run_end`
  (the name and signature lane/ontology uses; `main` re-pinned with a reference amendment).
  Check 64 runs it on a tempdir with `gnn_update` replaced by a recorder: capture and the rebuild
  happen, with 0 calls and no GNN state. Checks 57, 61 and 143 read the run end there.
- `scripts/ontology_gnn_rule_checks.py`: 23 of 23 proofs and neutralisations pass.

### 1b. After gnn-rule-check, items 6 to 9 (D-433)

- Item 6, version 1's material: section 3.1 now lists only generator tests made for training, by
  seeds and the generator's git tree, and rules out all of `benchmark/corpora/` and every other set
  by its test use. The label source in 3.4 is named: the generator's own listing and
  `relation_extract.py` on the same generated documents, never a run.
- Item 7, stale text: the `ontology_gnn.py` header and the state's `claim` field,
  `config/agent_harness.json`'s run-end line (19 entries) and its generator
  `scripts/build_agent_harness.py`, CLAUDE.md's `ontology/stores/` line and check 62's docstring are
  corrected. The orphan translation of "OGE GNN update skipped" is removed from
  `scripts/ui/localization_catalog.js`.
- Item 8, the re-pin: `python -m unittest execution_topology_checks` (from `scripts/`) on this
  lane's tip, after the D-432 re-pin (main a7974931..., `_ontology_run_end` 791bb0df... from null):
  28 tests, OK.
- Item 9: the loop tip (a0a4bd78, with D-433's check 242 fix) is merged into this lane.

## 2. The readings and the wording (rows 5 to 9, 12)

**Rows 5 and 6: Annex D readings.** These are proposed for the lead to record in DECISIONS.md;
Seckin's text is never edited.
- *D-S60 item 2*, read under D-S112: "material allowed to train on" is material made for the GNN's
  own training, domain- and case-agnostic. Python-confirmed findings and the operator's recorded
  decisions come from runs, so they are not training material for the GNN. Development gold already
  read may serve as measurement material, not as training material for the shipped base.
- *D-S61 items 2 and 4 (b)*, read under D-S112 and D-S114:
  - The lock governs the ontology store.
  - A new GNN version comes only from its own training, by its own command, when asked, and is
    adopted by the operator opening and closing the lock.
  - Item 4 (b)'s "update made from allowed material" is such a version.
  - Training on one user's material is a separate path that only that user's opt-in opens.

**Row 7: the update advisor** (`scripts/ontology_advisor.py`, `config/ontology_advisor.json`, on
lane/ontology). Proposed change for that lane:
- Its counts (Python findings and operator decisions since the frozen version) may propose an
  ontology store update to the operator, never GNN training.
- For the GNN it states only what section 3 gives it: whether a version from the GNN's own
  training exists and has been measured, whether someone has asked for one, and what the calibrated
  rule says that request lacks.

**Row 8: the routing DELTA draft** (`docs/ONTOLOGY_ROUTING_DELTA_DRAFT.md`, lane/ontology, the
`learning` clause). Proposed wording, to go to the ontology lane's owner through the lead:

> "The GNN is trained by its own training only, on material made for training, domain- and
> case-agnostic, never on what runs produce. The first version, the agnostic base, is produced by
> one such training and frozen read-only. A later version is made only when asked, by its own
> command, on declared material, and adopted only by the operator through the lock. After
> deployment, the GNN is trained further on one user's material only when that user asks for it,
> starting from the agnostic base. Its candidate sets keep learned_relevance false until a
> measurement says otherwise, and then carry the measured statement only."

**Row 9: the ontology lane's bar** (`docs/loop/stages/ONTOLOGY_LANE.md`). Change "the GNN's signal
is generator tests made for it and Python-confirmed findings only" to "the GNN's signal is
generator tests made for it only". Attempts 1 and 2 trained on generator tests alone, so no figure
changes.

**Row 12: cloud runs.** This follows from section 1. No run on an instance calls `gnn_update` any
more, so no instance trains its copy. `tools/cloud_run_observer.py` still names `gnn_update` among
the functions it watches, which is harmless: it watches calls and makes none.

**Row 13: the per-user opt-in, a loose end** (for `LOOSE_ENDS.md`, lead): an explicit per-user
opt-in for "improve accuracy with the GNN", off by default and recorded in the governance ledger.
Its training reads only that user's scope (`ontology_store` scopes), starts from the agnostic base
(version 1), and makes a version beside it that the user can roll back. Its state is requested,
and it waits for the deployment form. Until then the shipped base is the only version.

## 3. The ontology's life cycle (D-S114, D-418 as corrected by D-419)

### 3.1 Version 1: the agnostic base, produced by one GNN training

**Material, declared before training (D-433 item 6).** The material is only generator tests made
for the GNN's training. They are regenerated deterministically from their seeds into a scratch store
outside the repository by `tools/ontology_pairs_measure.py generate` (that tool is on lane/ontology,
not yet merged; version 1 waits for it), and turned into graphs by
Python there, never in `ontology/stores/`.

| Material | Identified by | Test use, ruled out |
|---|---|---|
| Generator tests, seeds 910001-910010 (f5 long-range), 910101-910110 (f2), 910201-910210 (f5), 910301-910310 (f6) | the seeds, and the generator code at git tree `94c308a39b803a55d67ee1aaa7fcb734aa63eda2` (`benchmark/generators` at this commit) | made for the GNN's training (ONTOLOGY_LANE.md); training side of attempts 1 and 2; never a test's held-out side |
| Generator tests, seeds 920001-920040 (ten each family) | the same | attempt 1's held-out block. It has been read, and under D-330 a read block may join later training. It is no gate, fresh, benchmark or worked-case item |
| Generator tests, seeds 930001-930040 (ten each family) | the same | attempt 2's held-out block, read once (D-359). The same rule applies |

Each graph's own sha256 is written into its `gnn-training-set-v1` declaration when it is built, and
the declarations' digests into version 1's record. Version 1's material is that list of
declaration digests.

**Not material, and why (each ruled out by its test use):**
- **All of `benchmark/corpora/`:** the catalogue records, clinical reference, device logs (both)
  and the two negotiation round pairs. They are test corpora with answer keys (CLAUDE.md: "run one
  before claiming domain agnosticism"). `benchmark/dev_cases/build_negotiation_case.py` builds
  worked cases from the negotiation pairs, and L7 ran "the catalogue test and both negotiation
  comparisons" as regression tests (DECISIONS.md, the L7 spend plan before D-097). They were listed here
  before D-433, wrongly.
- **The development suite's seeds** (`benchmark/dev_suite/SEEDS.json`, blob `c19fa9ab...`, used by
  L7 to L12) and the long-range seeds (`benchmark/long_range/SEEDS.json`, blob `af82e3f7...`):
  these are test seeds.
- **Every benchmark item:** ContraDoc, SciTab, PUBHEALTH, CLadder, Corr2Cause, development or not
  (D-S114 item 2).
- **The gate set, the fresh set, Test 1's held-out block 940001-940060 and its 60 ContraDoc
  documents, the calibration's held-out block (3.4), and every sealed item.**
- **Every run's output:** findings, operator decisions, captured provisions, and the store.

**What this costs in spread.** Four families of one generator are narrow, as D-413 noted. Version 1
is then "agnostic" only in the sense that it holds no domain's documents and no case. A wider base
needs new material made for training. It is not borrowed from test corpora, and it is declared in a
recorded edit before it is generated.

**What version 1 is:**
- the knowledge graph Python builds from that material (typed nodes and edges with provenance,
  `ontology_store`'s record shape);
- the GNN weights trained on it by `ontology_gnn.py train` (and, for the pair task, `ontology_pairs`
  with attempt 2's recipe);
- the training declaration's digest.

Relations the GNN proposes are recorded as candidates with provenance `gnn` and are never written
as confirmed edges. The whole is frozen by lane/ontology's lock (`ontology_lock_cli.py`) as
`ontology/versions/v1`, kept by digest.

**It depends on Test 1** (`KG_GNN_TESTS_PLAN.md`, on lane/cloud). If training does not help there,
version 1 is the static graph without trained weights, the life cycle's update has nothing to
improve, and the plan says so instead of training for nothing (D-S113 item 2).

### 3.2 Every run reads one version, read-only

A run reads the frozen version, writes nothing to it, and records the version and its digest in
`audit/ontology_version.json`, the run summary and the run report (D-S61 item 1, built on
lane/ontology). A version can be pinned, and an earlier version can be made the frozen one again,
which is the rollback (lane/ontology's lock command). This becomes true on the loop branch only when
lane/ontology is merged. Until then the loop's runs still capture into the store, though with this
lane none of them trains the GNN.

### 3.3 An update only on an explicit request

The command takes `--from vN`, a training-set declaration and a one-line purpose. It builds a
candidate version in a scratch store from version N plus the declared material, and records its
provenance: parent version, declaration digest, time, who asked, and purpose. It then measures the
candidate against version N with Test 1's bar, on development material not used to make it.

The candidate is adopted only if the operator opens and closes the lock for it; otherwise it is
kept and recorded. Runs never start the command, no scheduled job runs it, and nothing that runs
produce is declared material.

### 3.4 The calibration: what an update needs (D-418 item 2), development material only

**Question.** How does the held-out gain of an update over the base change with the number and the
kind of the new documents?

**Kinds, declared before any training.** Four properties are crossed:
- document family, the generator's own (f2, f5, f5 long-range, f6); after deployment, the user's
  own document types;
- length band, as the benchmark adapters' `ids.length_band` gives it;
- overlap with the graph: the share of the new documents' unit labels already in version 1, below
  or above the median;
- label source: the pairs the generator itself marks in its listing, against the relations
  `scripts/relation_extract.py` finds on the same generated documents, computed by Python in the
  scratch store. Neither comes from a run (D-433 item 6).

**Design:**
- k new documents of one kind, for k = 5, 10, 20, 40 and 80, with three seeds each. The new
  documents are fresh generator tests from seeds 950001-959999, declared in a recorded edit before
  any of them is generated, and never read by any test.
- Each update is trained from version 1 by the update command, in a scratch store.
- Each is measured on one fixed held-out block, generator seeds 960001-960060 (fifteen a family),
  never read by any other test.
- The metric is Test 1's: the share of gold pairs at K = 10 and K = 40, with 95 percent bootstrap
  intervals over documents.

**The margin, written before the read:** 5 points over version 1 at K = 10, as in Test 1.

**The rule, set from the measured curve:**
- *Minimum:* the smallest k at which the gain's lower interval bound is above zero and its mean
  reaches the margin, for that kind.
- *Target:* the k past which doubling adds less than 1 point.
- *Stop:* no gain at k = 80 for that kind, or a gain that falls as k grows.
- *Trigger:* a proposal, never a start. When the person asking has at least the minimum of a kind
  with a rising curve, the system proposes an update to them.
- The curve and the rule are written beside each other in this file once measured, with the figures
  of each point.

**Cost and time:**
- Per point: one small training (at most 80 documents) and one held-out read.
- Attempt 1's 80 documents took about 40 minutes of CPU, training and read together.
- The grid: 16 kind cells (2 × 2 × 2 × 2) are too many for three seeds before 12 November. It runs
  first on the two properties expected to matter most, overlap and label quality: 4 cells × 5 sizes
  × 3 seeds = 60 trainings, about 5 to 8 hours of CPU at 0 USD on the laptop.
- On image instances (D-S109): about 1 hour on four A10s, about 5.2 USD at the measured A10 rate
  (D-257). The full 16 cells would cost about four times that.
- It runs after the image, as the lead decided, and only after Test 1 passes.

### 3.5 The system states what it lacks (D-418 item 3)

From the calibrated rule, for the documents a person offers for an update, by kind, the system
writes one line per kind. For example: "18 documents of kind long, high overlap, gold-marked; the
measured minimum is 20: 2 more are needed", or "this kind showed no gain up to 80 documents: an
update from it is not proposed". It is shown in the console and the command line, and is a proposal
only.

### 3.6 The user opt-in starts from the agnostic base (D-418 item 4)

A user's update chain starts from version 1, never from another user's version. It never merges
into the base, and it is off by default (row 13 above).

## 4. What fits before 12 November

- **Done:** the code of section 1 (this lane, for the vekil check before its merge).
- **Possible on 10 November:**
  - Test 1, on CPU, after its vekil check and the go;
  - then version 1's training, about 1.5 hours of CPU, once the material is declared.
- **Possible on 10 and 11 November, only after the image and Test 1:** the calibration's four-cell
  grid, about 5 to 8 CPU hours, or about 1 hour and 5.2 USD on four A10s.
- **Needs lane/ontology's lock merged first:** the frozen `v1`, pinning and rollback, and the update
  command's adoption step.
- **After 12 November:** the full sixteen-cell calibration, the "what it lacks" statement in the
  console, and the opt-in.
