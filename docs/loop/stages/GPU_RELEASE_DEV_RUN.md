# The GPU-release development run: preparation and plan (#297, D-694 item 1; lane contradoc-d652, 16 November 2026)

Seckin's yes (D-694 item 1, 15:10): one 3-item development run on Lambda, about 1 to 1.5 USD with its seal,
Shimmer only, on exposed items, once lane/vllm-yield's review has passed and it is merged. It was merged at
7412cfa8 (three review rounds, e8de197f). This document prepares the run; nothing is sealed or launched here.

## 1. What it shows

A5's ContraDoc run (15 November 21:16 to 21:58, 0.90 USD, all three entries void) stopped at the same place in
every entry: after the two auditors ran on vLLM, the producer could not load for EDITOR_CLERK because the server
still held about 15.8 of the A10's 22 GiB. #297's fix (VLLM-ROUTE-A, `scripts/vllm_link.yield_card`) shuts the
server down before any transformers model loads on its card, under one card lock, and starts it again on the next
routed call. The run shows, on the same three entries, that:
1. every entry reaches its end with exit 0 (A5: 0 of 3);
2. every routed call succeeds, and a hand-back (`vllm_server_yield`) comes before every transformers load that
   follows a routed call;
3. how many server starts a run makes and what they cost (OPEN_ITEMS 115: sleep mode is decided on this figure);
4. the card's peak memory, against A5's.
It is a speed and integrity run on exposed items, never a score: agreement figures, if read at all, are labelled
development and exposed.

## 2. Items and the seal

- **Items:** A5's three ContraDoc entries (`external/vllm_test/A5`: contradoc_17bf4968de5e, contradoc_5395dcc657ee,
  contradoc_572aac4f058c, exposed development entries already run once), so the result reads directly against A5.
  Two of the three bundle folders are kept on the laptop (17bf..., 5395...); the third (572a...) has an empty
  seal log there, since its bundle was sealed on Lambda. Each workload is taken by its sealed digests
  (`execution_manifest.json` `workload`; for 572a from the route S job's records on the instance file system),
  no new staging; a third entry whose digests cannot be found is replaced by role B's next exposed ContraDoc
  development entry and named so.
- **The seal** on Lambda through route S (standing order 85: the laptop writes only the request), from a commit
  at or after the next merge of the lead branch (7412cfa8 or later; every bound file changed since be9cfd30, so
  A5's bundles cannot be reused). Sealer flags as A5's: arm B3, `--vllm-agents VERIFIER,PRACTICE_AUDITOR`,
  `--aux-lock` the pinned aux_env.lock, `--vllm-memory-share 0.7`, `--vllm-max-model-len 28672`; the shipped
  topology and argv (report_optimized, paired review, both override flags).

## 3. The reading, written before the run

`tools/gpu_release_read.py` (check 488) on the three run folders, counts, seconds and bytes only:
- per entry: state, reached_end, exit code; calls by engine and agent; failures by engine and category;
  hand-backs, their requests and close seconds; loads and loads without their end; loads after a routed call with
  no hand-back between; server starts and their seconds; peak GPU memory;
- **the bar**: every entry completed, reached its end, exit 0; no failed routed call; a hand-back in every entry
  that routed a call and then loaded a model; no load without its end; no load after a routed call without a
  hand-back; at least one routed call in the run. Exit 2 when a line is not met.
Beside it, from the run's own records: minutes and USD per entry, against A5's 42 minutes and 0.90 USD for the
part it reached.

## 4. Cost, two ways (A10 at 1.29 USD an hour live)

| Part | Without the saving measures | With them |
|---|---|---|
| The seal | its own route S job: about 20 minutes, **0.43 USD** (A5's second seal job, 19:30 to 19:50) | the three bundles added to the next route S job that runs anyway for the re-seal: about 5 minutes more, **0.11 USD** |
| The run | 3 entries: A5's 42 minutes to the failure, plus the producer's load and EDITOR_CLERK and the rest of each entry (about 3 minutes each, from the 14 November REFPAIR entry's timeline, 9.3 minutes end to end), plus two server restarts (about 2 minutes cold each, OPEN_ITEMS 115): about 55 minutes, **1.18 USD** | the same 55 minutes, **1.18 USD** |
| Asset copy | 64 minutes of upload if it reads MISSING, **+1.38 USD** | MATCH on the Lambda file system, 0 |
| **All** | **1.61 USD**, 2.99 USD with the upload | **1.29 USD** |

The saving measures: the seal shares a route S job already planned; the asset copy is reused. Launched under the
loop guard with a cap of 1.5 times the forecast (A5's sealed hard ceiling rule). With them, the run is inside
D-694's 1 to 1.5 USD; without them it passes it, and the launch then waits for the lead's check against D-694.

## 5. What could stop it, and what then

- A start failure after the hand-back (the server cannot find its share once the producer has run): recorded as
  the route's named failure; the run's integrity then shows whether the transformers fallback carried the entry.
- A routed call refused for a constraint digest mismatch: a seal fault, the run is void and reported.
- A loss of the instance: the reaper's deadline holds; the run is reported void with its spend.

## 6. Before it can launch

The re-seal route S job on Lambda from the merged tip (D-674, D-705 item 6: every bundle is re-sealed); the three
workloads' digests read from the A5 bundles; the forecast against the cap written into the request; no other
precondition (lane/vllm-yield merged at 7412cfa8).
