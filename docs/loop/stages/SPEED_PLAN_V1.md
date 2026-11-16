# Speed plan v1: the runtime speed fix for v1.0, ready to run on Lambda at the freeze

Written 16 November 2026 by lane `speed-prep` (lead branch tip 6e63d91b). D-628 B puts "the runtime speed
fix for this version" after the full set and the interface check and before the first release (v1.0); D-628 A
lists the five cost measures; D-531 and D-532 (standing order 73) give the method: a small test that outputs
or accuracy are unchanged, then adopt. This plan changes no measured behaviour now. It names what dominates
a full run's time today, ranks the candidate changes, and fixes the Lambda measurement for each, with its
cost. The one piece built now is measurement tooling: `tools/launch_time_split.py` (check 445), which
reads saved run records only.

Sources, read as counts, seconds and names only: the D-S82 reference pair `external/s05/REFPAIR`
(refpair-a10 and refpair-a100 at 03054203, D-633; the only launch folders with full timing evidence left
after the 16 November loss, D-696), GATE_SCOREBOARD (gate-quick-1 rows), D-598 (agent time split of the K1
quick read), D-599 to D-601, D-608 to D-610, D-624, D-625, D-628, D-630, D-633, D-694, TIME_BUDGET.md,
IMAGE_PLAN.md (section 2), AFTER_V1_PLAN (speed-up sections), OPEN_ITEMS 38, 94, 95, 102, 115, issues
#217, #241, #256, #264 and #297. `output/` in the main checkout holds no cloud run timing (only laptop runs
of September), so nothing there is used.

## 1. Where a run's time goes today

### 1.1 One launch, split second by second (refpair-a10, three exposed reference entries)

`py -3.12 -X utf8 tools/launch_time_split.py split external/s05/REFPAIR/bundles/contradoc_0436316e6bb3_A10_s2_B3`
(gpu_1x_a10, 1.29 USD an hour, 2,457 s billed, 0.88 USD):

| Part | Seconds | Share | What is in it |
|---|---|---|---|
| Provider boot | 201 | 8.2% | launch request to the first ssh phase |
| Setup | 726 | 29.6% | asset copy probe 292 (hash of the 22 GB archive on the mount), asset copy use 211, pinned wheel install 91, support transfer 37, archive integrity 32, extraction 19, five short phases 39 |
| Between entries | 204 | 8.3% | next entry's bundle transfer 101 (two transfers), park, integrity, extract, pack, hash and download about 8 s each |
| Workloads | 1,171 | 47.7% | the three runner processes (589, 247 and 335 s) |
| Tail | 66 | 2.7% | stop, GPU state, last pack, hash, download |
| Controller gaps | 1 | 0.0% | between phases |
| Termination wait | 87 | 3.6% | requested to verified terminated |

Inside the three workloads (1,171 s):

| Part | Seconds | Share of workload |
|---|---|---|
| Generation (union of generate intervals) | 919 | 78.5% |
| Outside the pipeline (process start, admission, model hashing) | 110 | 9.4% (37 s an entry) |
| Model loads (12 loads, four an entry: producer, auditor, Phi, producer again) | 100 | 8.6% (33 s an entry) |
| Rest of the pipeline (Python, embedding, scheduling) | 43 | 3.6% |

Inside generation, by agent (A10; service seconds include each agent's first model load):

| Agent | Service s | Calls | Output tokens | Decode tok/s | Prefill s |
|---|---|---|---|---|---|
| VERIFIER | 345 | 3 | 4,112 | 12.6 | 9.7 |
| PROCESSOR (DECODING-B constraint) | 293 | 7 | 2,487 | 8.6 | 3.5 |
| ARCHIVIST | 99 | 3 | 404 | 7.0 | 7.6 |
| PRACTICE_AUDITOR | 80 | 6 | 1,260 | 17.9 | 9.1 |
| EDITOR_CLERK | 50 | 3 | 97 | 6.3 | 4.3 |
| LEGAL_ANALYST | 46 | 4 | 306 | 8.9 | 11.4 |
| SPEECH_ACT_TAGGER | 42 | 3 | 299 | 8.9 | 8.0 |
| CITATION_RESOLVER | 38 | 3 | 281 | 9.0 | 6.7 |
| AUDITOR896, EMBEDDING | 55 | (classifier, embedding) | | | |

### 1.2 What this says

1. **Decode dominates.** Prefill is 60 s of 919 s of generation (6.5%); the rest is token-by-token decode
   at 6 to 18 tokens a second. The static (shared) part of the prompts is 48% of their characters, so a
   prefix cache on this path could save at most about 3% of generation.
2. **Decode is bound by per-step overhead, not the card.** The A100 decodes no faster (PROCESSOR 7.0
   against 8.6 tokens a second, VERIFIER 13.0 against 12.6; D-633's workload factor 0.908). A faster card
   does not help; an engine that cuts the per-step cost (fused 4-bit kernels, CUDA graphs) or spreads it
   over several sequences at once (batching a wave's independent calls) does. Today one call runs at a
   time (`maximum_concurrency` 1, one worker per lane in `scripts/execution_scheduler.py`).
3. **Run-to-run variance is large and sits in VERIFIER.** The same first item took 589 s here and 332 s in
   an earlier A10 run (D-633's stated limit); here its VERIFIER reply was 10 KB (4,112 tokens, 300 s) while
   the A100 run's was 439 bytes. A speed figure from one run of three items is a direction; every move below
   runs each item twice and reads seconds per output token beside raw seconds.
4. **An early stop on a closed reply saves nothing.** Across the six entries of both runs (64 JSON replies beside the
   classifier's 28 labels, about 50 KB), the bytes after the first closed JSON object total 9 (three fences). D-598's "stopping after a closed reply" is
   dropped on this evidence.
5. **Fixed costs per entry are about 170 s** (37 s outside the pipeline, 33 s of model loads, about 100 s
   between entries), against 150 to 510 s of generation. **Fixed costs per launch are about 1,080 s**
   (boot, setup, tail, termination: 18 minutes), amortised over the entries of the launch.

### 1.3 At full-set scale (projection from recorded figures, not a measurement)

The quick read (GATE_SCOREBOARD, gate-quick-1 K0 old path, 15 November) used 438 instance minutes for 40
ContraDoc documents (11.0 min a document, 0.24 USD) and 100 minutes for 13 SciTab tables (7.7 min a table).
The claim set (GATE_SET.md) is 230 ContraDoc documents and at least 352 SciTab claims (about 59 tables at the
quick subset's 6 claims a table). On the old path that is about 2,530 plus 454 instance minutes, about 50
hours and **about 64 USD for the system arm**, before any measure here. The D-598 split of the K1 quick read
puts PROCESSOR at 31% of time, ARCHIVIST 23, VERIFIER 8, EDITOR_CLERK 6, AUDITOR896 6, CITATION_RESOLVER 5,
SPEECH_ACT_TAGGER 4, LEGAL_ANALYST 3; PRACTICE_AUDITOR makes no calls in the gate configuration, while on
rule-heavy product documents its paired judging calls take 60 to 89% of the wall time (TIME_BUDGET.md).

## 2. Candidate changes, ranked by expected saving

Full-set figures scale each per-entry saving by the quick read's 11.0 instance minutes a document against section 1.3's 64 USD; they overlap and do not add. Per-entry savings are against the reference mix on the A10 (459 s an entry billed outside the launch's fixed
part, 390 s of it workload). "Bound" means a file in the controller binding (`CONTROL_FILES` in
`tools/prepare_ordinary_final_run.py`, CONTROLLER-BINDING): changing it forces a re-seal of every bundle.
Every file under `scripts/`, `config/` and `benchmark/` travels in the sealed project archive, so any change
there also needs a new seal, but does not invalidate bundles already sealed. "Pinned" means a pipeline
function in `benchmark/fixtures/topology_reference_contract.json` (101 functions; a genuine change is an
amendment there, see the reference AST pin). Per D-631 and D-630 item 5, no bound change merges before the
full set's bundles are sealed and launched; D-628 B already puts this work after the full set.

| Rank | Change | Expected saving | Touches | Bound file | Pinned function | PREFILL-E decision id | Measured by (FACTORS-A, one machine type) |
|---|---|---|---|---|---|---|---|
| 1 | **vLLM for every local generation, with a wave's independent calls sent together** (#264, D-609, D-630 part B; after #297's card hand-back, merged) | generation 2 to 3 times faster is the planning range (A5 was void, no figure): about 150 to 200 s an entry, 33 to 44% of the per-entry time; full set about 15 to 19 USD of the 64 | `scripts/vllm_route.py` (`BACKENDS` adds `local_producer`, the adapter, the constraint port), `scripts/vllm_link.py`, `scripts/execution_scheduler.py` (more than one call in flight per lane), the aux env layer (IMAGE-A) | yes: the controller's aux-env phases and vLLM route (#264 item 2) | `_gather_or_serial` only if the wave submission changes there; the route itself sits outside the pins | **yes**: the engine, its kernel and its prefill differ from D-063's sdpa one-shot; batch invariance named; D-608 makes differences a stability finding, D-625 is the bar | M1 and M2 against M4 on the reference set, gpu_1x_a10; gold bar run under #264 |
| 2 | **Less controller time between entries**: the next entry's bundle uploaded while the current workload runs; park, integrity and extract as one remote step; pack, hash and download as one | about 65 to 80 s of the 100 s an entry (14 to 17%); full set about 6 to 8 USD | `tools/ordinary_final_cloud.py` (phase list, `FIRST_POLL` 2 and `POLL_INTERVAL` 10 unchanged or shortened), `tools/cloud_run_common.py` | **yes** | no | no | M4 against M0: setup, between-entry and tail categories; reviews byte-identical |
| 3 | **Warm models within a batch**: `resident_limit` 2 so producer and auditor stay on the 24 GB card (peak reserved today 11.6 GB with one resident), and the session's models hashed once after the read-only bind (IMAGE-A) instead of per entry | about 40 to 60 s of the 70 s an entry of loads and start (TIME_BUDGET's 50 s estimate), full set about 4 to 6 USD; under vLLM it becomes keeping the servers up across entries (open item 115's sleep mode) | `tools/ordinary_final_run.py` (`TOPOLOGY`, the per-entry model hash), `scripts/final_models.py` (eviction) | **yes** (`ordinary_final_run.py`) | no | no | M3 against M0 (transformers fallback only); reviews byte-identical |
| 4 | **Image layers by default** (IMAGE-A, IMAGE_PLAN section 8: one line in the sealer, the env layer from its build record) instead of the asset copy probe and copy and the wheel install | about 200 to 300 s a launch (M2 of 12 November reached its workload 12.0 minutes after launch, this launch 15.5); about 10 to 15 s an entry in a 20-entry launch, 70 to 100 s in a 3-entry one; full set about 1 to 2 USD | `tools/prepare_ordinary_final_run.py` (`--image-layers` default; preparation file, hashed in the manifest, not in the binding) | no | no | no | M4's setup category against M0's |
| 5 | **A cheaper constraint step** (DECODING-B): the producer decodes at 8.6 tokens a second against VERIFIER's 12.6 on the same card; if the gap is the per-step mask in Python, a cached or vectorised mask with the same admitted set removes it | up to about 28 s an entry (a bound; the per-step cost is not recorded), full set at most about 3 USD; survives the engine change, since the constraint runs per step on vLLM too | `scripts/contract_decoding.py` (`ContractProcessor`) | no | no | no (decoding values unchanged; DECODING-B checks 263 and 297 hold the language) | M6: per-step timing over saved replies with the real tokenizer, same admitted sets on every step |

Below the top five:

- **Prefix caching on the local models** (D-628 A item 1): at most about 3% of generation on today's path
  (section 1.2 item 1). Measured only inside vLLM (automatic prefix caching is one server flag) and only if
  M2 shows prefill above 10% of generation, which becomes likely once decode is faster. PREFILL-E: needs a
  decision id (a prefill setting). For the cloud reference, prompt caching is already applied (D-610 cut 2).
- **Early stop on a closed reply**: about 0 s (9 bytes after the close in 64 JSON replies). Dropped.
- **Machine type by speed per dollar** (D-628 A item 4): the A100 is 0.908 times the A10's speed at about
  1.7 times its cost per item (D-633). Decode is per-step bound, so no faster type is expected to pay; a
  type not in `tools/cloud_run/gpu_speed_order.json` `order` cannot be chosen without a recorded change.
  No move planned.
- **Batched PRACTICE_AUDITOR calls** (#256, parked until after the measurement, D-601): no calls in the gate
  configuration, the biggest share on rule-heavy product documents. With vLLM it is the same mechanism as
  rank 1's wave submission and is measured there.
- **Reuse of quick-read outputs** (D-628 A item 5, D-610 cut 4): a cost measure for the report, not a
  runtime speed fix.
- **The 37 s outside the pipeline per entry** is not split in the records (process start, imports,
  `final_models.verify_runtime`, model hashing). A timing line would be a bound change
  (`tools/ordinary_final_run.py`); until then rank 3 carries it as a bound.

Two of these interact: rank 3's loads become server starts under rank 1 (30 s warm, 2 minutes cold, A5),
so rank 3 is measured on the transformers path only if vLLM fails its bar, and otherwise as "servers kept
up across entries".

## 3. The Lambda measurement plan

### 3.1 Fixed for every move

- **Items.** The D-S82 reference set `machine-reference-v1` (FACTORS-A `reference_set.items`): three exposed
  B3 entries already run on the A10 with integrity passed. Each runs **twice** in a move (six entries), for
  VERIFIER's run-to-run variance (section 1.2 item 3).
- **Machine.** gpu_1x_a10, us-east-1, every move. `launch_time_split.py compare` and
  `factor_record.attribute` (`require_machine_pair`) refuse any other pairing.
- **Launch.** LOOP-LAUNCH-A: budget guard, ledger, reaper, cap; one move per launch, its cap at most 3 USD
  (D-629 item 2: a move of 3 USD or less goes ahead). Exposed development items only, no sealed material.
- **Reading.** After each move: `py -3.12 -X utf8 tools/launch_time_split.py split <session> --out
  <session>/time_split.json`, then `compare` against the move it isolates, then `tools/factor_record.py
  compare` and `attribute` on the two factor records. A saving is credited to a change only when its pair
  differs in that change alone (FACTORS-A); otherwise it is one joint row.
- **Bars.** Moves that change no generation (M3, M4, M6) pass only with every entry's `review_data.json`
  byte-identical to its isolating partner (or, for M6, the same admitted set at every step). Engine moves
  (M1, M2, M5) report agreement per D-608 as a stability finding; adoption is decided by D-625's gold bar
  on the development set, run under #264, not by these six entries. Speed figures: billed seconds per
  entry, workload seconds, generation seconds per output token, prefill seconds per 1,000 input tokens.
- **Seals.** Every bundle is sealed on Lambda through route S (D-668, D-674). The first seal job of
  15 November sealed 8 bundles for 0.49 USD.

### 3.2 The moves, in order

Cost forecasts at 1.29 USD an hour. "Expected" uses the recorded per-entry figures (section 1.1);
"worst" assumes every entry as slow as the slowest recorded (589 s) and, for vLLM, no speed gain and a
cold server start (2 minutes) for each of three models in every entry.

| Move | What | Isolates | Bundles | Expected minutes | Expected USD | Worst USD | Cap USD |
|---|---|---|---|---|---|---|---|
| S1 | Seal job: M0's six bundles on the frozen v1.0 commit | | 6 | 25 | 0.50 | 0.70 | 1.0 |
| M0 | Baseline: frozen code, transformers path, current controller | | 6 | 67 | 1.44 | 1.87 | 2.5 |
| S2 | Seal job: M4, M1, M2 bundles on the speed branch (one re-seal for all bound changes, ranks 1, 2, 4) | | 18 | 30 | 0.65 | 0.90 | 1.0 |
| M4 | Controller and image changes only (ranks 2 and 4), transformers path | M4 vs M0: controller, image | 6 | 57 | 1.22 | 1.80 | 2.5 |
| M1 | M4 plus vLLM for every local generation, one call at a time | M1 vs M4: engine | 6 | 48 | 1.02 | 2.41 | 2.9 |
| M2 | M1 plus a wave's independent calls in flight together | M2 vs M1: concurrency | 6 | 39 | 0.83 | 2.41 | 2.9 |
| M6 | Constraint step timing (rank 5) over the saved PROCESSOR replies of M0, CPU only, cheapest instance | M6 old vs new mask, same replies | 0 | 10 | 0.10 | 0.25 | 0.5 |
| **Planned total** | | | | **276** | **5.76** | **10.34** | |
| M5 (if M2's prefill is above 10% of generation) | M2 plus automatic prefix caching | M5 vs M2: prefill | 6 (sealed in S2) | 39 | 0.83 | 2.41 | 2.9 |
| M3 (if vLLM fails D-625's bar) | M4 plus `resident_limit` 2 and one model hash a session (rank 3), transformers | M3 vs M4: residency | 6 (one more seal job, 0.30) | 50 | 1.38 | 2.05 | 2.5 |
| **With both conditional moves** | | | | **365** | **7.97** | **14.80** | |

Each move stays under 3 USD at its worst case. Order and time: S1 and M0 run as soon as the code is frozen
(about 1.5 hours with reading). S2 follows once the speed branch passes its gate. M4, M1 and M2 are
independent once sealed and run side by side on three instances (no instance limit, D-S95; the budget rule
decides), about 1 hour of wall time; M6 runs beside them. Planned wall time about **3.5 hours** from the
freeze (S1 25 min, M0 67 min, S2 30 min, the parallel moves about 60 min, reading about 30 min); about
**5 hours** if every move runs one after another; plus about 1 hour if M5 or M3 is needed.

### 3.3 What each move must record

Already in the records today, read by `launch_time_split.py`: every phase's timing, the telemetry summary
(phase latencies, model lifecycle, per-agent service, generation union, resources), generation
observations, prompt structure, reply records' prefill block. Needed and not yet present, so built with
the speed branch (bound changes, sealed in S2): vLLM's server start seconds and request seconds per call
are already in the reply record's `attention` block (`scripts/vllm_route.py`); the wave submission must
record the number of calls in flight per wave; open item 115's `vllm_server_yield` events count server
restarts. The outside-the-pipeline 37 s stays unsplit unless a timing line is added to the runner (open item 138).

### 3.4 Prerequisites and decisions

- #297's fix is merged (16 November); its 3-item development run (D-694 item 1) shows the card hand-back on
  Lambda before M1 depends on it.
- vLLM part B (the producer with its adapter and the DECODING-B constraint on the server, D-630) is built
  and passes its fixture proofs before S2.
- **Decision ids to request from the operator before S2** (PREFILL-E): the engine setting for every
  producer and auditor generation on vLLM (M1), the in-flight batching with batch invariance (M2), and, if
  run, automatic prefix caching (M5). M0, M3, M4 and M6 need none.
- Rank 3 under vLLM (servers kept up across entries) needs open item 115's sleep-mode measurement first.

## 4. Built now

- `tools/launch_time_split.py`: `split` (one or more collected session folders; several are summed only on
  one machine type) and `compare` (after minus before; refused across machine types). Standard library,
  reads only, no model; prints counts, seconds and USD with entries numbered, never a folder name, id or
  text. Section 1.1's tables come from it.
- `tools/launch_time_split_checks.py`: six proofs on an invented session (sub-steps not counted twice,
  every billed second in one category, the workload split, per-agent sums with the closed-object tail, no
  identifier in the output, no comparison across machine types), each neutralise, fail, restore, pass.
  Gate check 445. Its peak memory is that of a small standard-library process, far below 400 MB.
- Nothing else: no runtime path, bound file or pinned function is changed by this lane.
