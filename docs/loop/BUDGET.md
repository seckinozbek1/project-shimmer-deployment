# Loop budget

The Lambda budget for this loop is 50 USD in total (Part II, H3), counted from the start of S0, taken as the ledger's opening line (2026-10-27 03:16 UTC; the session started at 03:00 UTC and nothing was spent before the ledger opened). This file shows the running total, the forecast against the actual cost of every run, and what remains. It never holds an instance id. The private ledger (`docs/loop/private/budget_ledger.jsonl`) holds the detail.

> Note (2026-10-27 13:23 +0300): since the operator's decision D-S9 (09:34 UTC) the budget is 70 USD with a 69 USD hard stop; see the allocation table from 09:34 UTC below and DECISIONS.md D-030 and D-031.

## Running total

| Date (UTC) | Event | Instance minutes | Instance cost (USD) | Storage share to date (USD) | Total spent (USD) | Remaining (USD) |
|---|---|---|---|---|---|---|
| 2026-10-27 03:16 | Budget opened at S0. No instance running, no orphan. | 0 | 0.00 | 0.00 | 0.00 | 50.00 |
| 2026-10-27 09:34 | Budget raised to 70 USD by the operator (D-S9); reaper hard stop 69 USD; seven-day launch limit 95%. No instance has run. | 0 | 0.00 | 0.03 | 0.03 | 69.97 |

## Allocations (IV.3)

| Allocation | USD | Notes |
|---|---|---|
| S5 development runs | 18.00 | S6 may spend only what S5 leaves unused. |
| S8 sealed evaluation | 24.00 | Reserve pays only infrastructure re-runs in S8. |
| Smoke runs (S12 item 8) | 3.00 | |
| Reserve | 5.00 | Storage share is charged here first. Storage forecast to the loop's end: 0.13 USD a day for 30 days (no pace measured yet) = 3.90 USD, so 1.10 USD of the reserve remains for re-runs. |

## Prices

Read live from the provider adapter's `instance-types` projection (`metadata.hourly_rate`) at each launch. Never typed in.

| Read at (UTC) | Type | USD per hour | Regions with capacity |
|---|---|---|---|
| 2026-10-27 03:13 | gpu_1x_a10 (reference for the type rule, IV.3) | 1.29 | us-east-1, us-west-1 |

Other single-GPU types read at the same time, for the type fallback (another type only at no more than twice the A10's price, so at most 2.58 USD an hour): A6000 1.09 (no capacity), RTX 6000 0.69 (no capacity), A100 PCIe 1.99 (no capacity), A100 SXM4 1.99 (us-east-1, us-west-2), GH200 2.29 (no capacity).

## Measured timings the forecast uses (S0 step 20)

All runs below were single A10 instances in us-east-1 at 1.29 USD an hour, running the ordinary final controller with the upload path (no asset-copy MATCH). Billed minutes run from the provider's active-start time to the controller's observed termination.

| Run | Billed minutes | Cost (USD) | Upload (min) | Workload (min) | Source |
|---|---|---|---|---|---|
| v5 | 54.5 | 1.172 | 37.5 | 7.1 | `docs/fix/ordinary_final_cloud_run_v5/cost.json`, `assets_transfer_timing.json`, `ordinary_workload_timing.json` |
| v6 | 52.8 | 1.135 | 37.1 | 6.3 | same files under `ordinary_final_cloud_run_v6/` |
| v7 | 55.4 | 1.191 | 37.7 | 8.9 | same files under `ordinary_final_cloud_run_v7/` |
| v8 | 53.9 | 1.158 | 36.9 | 7.9 | same files under `ordinary_final_cloud_run_v8/` |
| v9 | 53.7 | 1.155 | 37.8 | 6.8 | same files under `ordinary_final_cloud_run_v9/` |
| v12 | 54.6 | 1.174 | 37.4 | 6.3 | same files under `ordinary_final_cloud_run_v12/` (local, under the ignored `docs/fix/`) |

v10 and v11 have no `cost.json` on this laptop. The v12 phases, from its local `*_timing.json` files: boot to SSH ready and support transfer about 4.9 minutes; upload 37.4 minutes; after the upload (integrity hash 0.3 min, filesystem seed 0.5 min, extract, environment, pinned wheels 1.3 min) about 3.0 minutes; workload 6.3 minutes; stop, evidence and collection about 3.0 minutes.

**Forecast formula (IV.3).** (setup + attach or upload + post-upload setup + workload + collection) times the live price, times 1.3. With the upload: about (4.9 + 37.4 + 3.0 + W + 3.0) minutes. With an asset-copy MATCH: the upload is replaced by the attach, copy and hash, not yet measured on this filesystem (v12 measured only the write side, 31.9 s); until a MATCH run is measured, the forecast keeps the upload.

## Forecast against actual, per run

| Run | Purpose | Forecast (USD) | Cap (USD) | Actual (USD) | Variance |
|---|---|---|---|---|---|
| (none yet) | | | | | |

## Allocation from 2026-10-27 09:34 UTC (operator decision D-S9; supersedes the table above)

| Allocation | USD | Notes |
|---|---|---|
| S5 development runs | 24.00 | S6 may spend only what S5 leaves unused. |
| S8 sealed evaluation | 36.00 | Reserve pays only infrastructure re-runs in S8. S4e item 2's sizing rule is re-run with this figure when the preregistration is completed at the end of S5. |
| Smoke runs (S12 item 8) | 3.00 | |
| Reserve | 7.00 | Storage share is charged here first (forecast 3.90 USD to the loop's end). Unused allocation rolls forward. |

The reaper's hard stop is 69 USD and the controller's budget guard counts against 70 USD; both read the budget from the ledger's latest budget line since commit `addf658` (merged `e1ca581`, D-031); the scheduled reaper's first run after the merge, at 2026-10-27 10:06:59 UTC, reported budget 70 and hard stop 69. No new launch while five-hour usage is at or above 70 percent or seven-day usage at or above 95 percent.

## How a launch is capped (since S2 checker round 2, 2026-10-27)

The per-run cap is min(1.5 x forecast, ceiling - spend - caps of running loop instances - storage forecast), where the ceiling is min(hard stop, budget - 1), both read from the ledger's latest budget line (69 USD now); a line whose hard stop equals its budget still keeps the one-dollar margin. An open launch accrues spend only up to its recorded deadline; past it, with no instance of its name listed, the reaper closes it with one termination line (reason `intent_without_instance`, or `instance_not_listed_charged_to_deadline` when the instance is gone), charged to the deadline. That charge is a ceiling, counted as actual spend and never refunded. The line goes to every ledger file that holds the launch, so a launch recorded only in R's ledger is closed in R's ledger.

## Stage boundary: S2 closed (2026-10-27 15:23 +0300)

Spend so far: 0.00 USD on instances; the storage share is 0.05 USD (the reaper's reading at 12:21:59 UTC). Running loop instances: none (the reaper's provider listing at 12:21:59 UTC listed 0). Storage forecast to the loop's end: about 0.13 USD a day; pace so far is about 28 percent of the work in 9.5 hours, so the 30-day placeholder stays until S5's pace can be measured.

## Stage boundary: S3 closed (2026-10-28 11:32 +0300)

Spend so far: 0.00 USD on instances; the storage share is 0.16 USD (the reaper's reading at 08:31:59 UTC on 28 October: total 0.1585 USD). Running loop instances: none (the same provider listing listed 0; the reaper's last run was under 10 minutes old). Storage forecast to the loop's end, now from a measured pace: S0 to S2 and most of S3 and S4 (about 31 percent of the weighted work, D-035 weights) took about 13 working hours on 27 October, with an overnight shutdown of about 16 hours; at that pace, with the cloud waits of S5 and S8 and one more lost day as margin, the loop ends in about 4.5 days, so the storage forecast is 0.13 x 4.5 = 0.59 USD (estimate), charged to the reserve first. This replaces the 30-day placeholder (3.90 USD).

## Stage boundary: S4 closed (2026-10-28 12:31 +0300)

Spend so far: 0.00 USD on instances; the storage share is 0.16 USD (the reaper's reading at 09:27:00 UTC: total 0.1635 USD). Running loop instances: none (the same listing listed 0; the reaper's last run under 10 minutes old). Storage forecast to the loop's end: unchanged from the S3 boundary this morning, 0.59 USD (estimate).

## S5 launches: forecast before, actual after (P6)

| Launch | Purpose | Forecast basis | Forecast F (USD) | Cap (USD) | Actual minutes | Actual (USD) |
|---|---|---|---|---|---|---|
| L1 (2026-10-28 12:51 +0300) | dev-smoke, clinical sheet, exposed | 55 minutes (setup 4.9, upload 37.4, attach probe 3.0, workload 6.3, collection 3.0; the upload kept until a MATCH is measured), A10 us-east-1 at 1.29 USD an hour (live, 09:49 UTC), times 1.3 | 1.54 | 2.31 | 23 (ledger); workload 7.6, asset-copy probe 3.2 and use 0.3, wheels 1.3, support transfer 1.1 (phase timings) | 0.49 (ledger; the run report estimates 0.48). Variance: actual 32 percent of forecast, because the asset copy was a MATCH (first measured MATCH: no 37-minute upload). Overhead without the upload measured at 15.4 minutes (billed minus workload), against the 13.9 estimate; later forecasts use 15.4 |
| L2 (2026-10-28 14:53 +0300) | dev-dryrun, ContraDoc 5 and SciTab 5, B3 and B1 (five passes), exposed | 201 minutes (overhead 15.4 measured; B3 7.6 a document; B1 7 an entry; 2 an entry), A10 at 1.29, times 1.3 | 5.62 | 8.43 | 148 (ledger); 20 entries, about 6.6 minutes an entry after the 15.4-minute overhead; MATCH again | 3.18 (ledger). Variance: actual 57 percent of forecast. All 10 B3 entries failed (corrected after diagnosis: 1 ContraDoc entry out of GPU memory, INC-015; 1 crashed on a VERIFIER reply that was not an object, auditor_pairs.py line 317; 8 reached the end semantically incomplete because PROCESSOR broke its contract in 12 of 20 partitions), all 10 B1 entries passed (five passes each) |
| L3e (2026-10-28 19:24 +0300) | dev-e-evidence, ContraDoc 1 and FinDVer 1, B3 under E and B1 measurement passes plus replay, exposed | 99 minutes (D-062), A10 at 1.29, times 1.3 | 2.77 | 4.16 | 157 (ledger); the FinDVer B3 entry alone ran about 110 minutes (forecast 40); the FinDVer B1 entry did not start before the workload stop; MATCH | 3.38 (ledger). Variance: actual 122 percent of forecast, inside the cap |
| L4a (2026-10-28 23:19 +0300) | dev-dryrun-l4a, ContraDoc 2, SciTab 2, ContractNLI merged 1 (band B), B3 under A and B1 base and tuned, exposed | 216 minutes (D-064 as attacked: 15.4 + 4 x 14 + ContractNLI B3 about 110 + B1 15 + 10 x 2), A10 at 1.29, times 1.3 | 6.04 | 9.06 | 121 (ledger); B3 workload under A: ContraDoc 4.1 and 6.2, SciTab 2.3 and 4.4, ContractNLI merged band B 50.5; no out-of-memory failure; every B3 entry semantically incomplete (PROCESSOR contract), every B1 entry passed | 2.60 (ledger). Variance: actual 43 percent of forecast |
| L5v (2026-10-29 03:04 +0300) | d068-verification: clinical sheet, device-log flawed and clean twin, B3 only, exposed | 45 minutes (D-069), A10 at 1.29, times 1.3 (unrounded 1.258: 0.75 hours x 1.29 x 1.3; recorded as 1.27 at the time, a rounding slip, S5 checker round 1) | 1.27 (1.258 unrounded) | 1.90 | 61 (ledger); MATCH | 1.31 (ledger). Variance: 104 percent of the unrounded forecast (103 percent of 1.27) |
| L4b (2026-10-29 11:38 +0300) | dev-dryrun-l4b, ContractNLI merged band A and band B, FinDVer band D, B3 and B1 base and tuned, exposed | 271.9 minutes (D-073: 15.4 + B3 36 + 72.5 + 110 + B1 8 + 8 + 10 + 6 x 2), A10 us-east-1 at 1.29 USD an hour (live, 08:2x UTC), times 1.3 | 7.60 | 11.40 | 204 (ledger); B3 entries: ContractNLI band A 29 minutes (semantically incomplete), band B refused at 6.8 minutes (INC-019), FinDVer band D about 97 minutes (semantically incomplete); B1 entries 9, about 10 and about 30 minutes; MATCH | 4.39 (ledger). Variance: actual 58 percent of forecast |
| L6 (2026-10-29, D-077) | dev-dryrun-l6, the five L4a documents again under D-068, ContractNLI band B under D-076, the synthetic and the negotiation multi-round cases, B3 only, exposed | 248.9 minutes (15.4 + 67.5 + 70 + 39 + 41 + 8 x 2), A10 at the live price, times 1.3 | 6.96 | 10.44 | 174 (ledger); entries 1 to 6 done (ContractNLI band B completes under D-076, 81.8 minutes); the operator stopped the laptop at 18:15 during entry 7, cleanup terminated the instance (D-079) | 3.74 (ledger). Variance: actual 54 percent of forecast |
| L6s (2026-10-29, D-077) | dev-span-l6s, ContractNLI span parts on one agreement, B3 only, ended by the workload stop, exposed | 50 minutes, A10 at the live price, times 1.3 | 1.40 | 2.10 | 0: not launched (the 18:15 stop); resealed as L6s2 after the hidden-window change (D-079) | 0.00 |
| L6m (2026-10-29, D-079) | dev-multiround-l6m, the synthetic family 4 case and the negotiation case (multi-round), B3 only, resealed after the 18:15 stop and the hidden-window change, exposed | 99.4 minutes (15.4 + 39 + 41 + 2 x 2), A10 at the live price, times 1.3 | 2.78 | 4.17 | 46 (ledger); the synthetic case refused at the multi-round phase (INC-023), the negotiation case refused the same way; MATCH | 0.99 (ledger). Variance: 36 percent of forecast |
| L6s2 (2026-10-29, D-079) | dev-span-l6s, the L6s bundle resealed at ee8fa6a | 50 minutes (as L6s), A10 at the live price, times 1.3 | 1.40 | 2.10 | 26 (ledger); workload 9.1 minutes, the span-part B3 run out of GPU memory (D-083); MATCH | 0.56 (ledger). Variance: actual 40 percent of forecast |

## S5 closing (2026-10-29 22:30 +0300)

Instance spend in S5: 20.64 USD (ledger: L1 0.49, L2 3.18, L3e 3.38, L4a 2.60, L5v 1.31, L4b 4.39, L6 3.74, L6s 0.00, L6m 0.99, L6s2 0.56), against the S5 allocation of 24.00, so 3.36 USD is unused (the only money S6 may spend, IV.3). The reaper's reading (`reaper_status.json`, 2026-10-29 19:56:59 UTC; the same reading as the S5 report's stage boundary, S5 checker round 2): total spend 20.99 USD (20.9904), 0 loop instances listed, budget 70, hard stop 69. Storage share to date, as the difference: 20.99 - 20.64 = 0.35 USD. Remaining against the 70 USD budget: 70.00 - 20.99 = 49.01 USD (48.01 below the 69 USD hard stop). No overrun reached the reserve.

## Allocation from 2026-10-29 21:10 UTC (operator decision D-S12; supersedes the tables above)

| Date (UTC) | Event | Instance minutes | Instance cost (USD) | Storage share to date (USD) | Total spent (USD) | Remaining (USD) |
|---|---|---|---|---|---|---|
| 2026-10-29 21:10 | Budget raised to 100 USD by the operator (D-S12, Annex D, 30 October 00:05, revised 00:10 +03:00); reaper hard stop 99 USD; `budget_change` line appended to the private ledger at 21:10:04 UTC; the reaper's `budget_figures` reads (100.0, 99.0) from it. No instance running. | 0 | 20.64 (S5 so far) | 0.35 (S5 closing reading) | 20.99 | 79.01 |

| Allocation | USD | Notes |
|---|---|---|
| S5 development runs | 30.00 | The 24.00 before, plus 6.00 for D-S12 item 1 (open items 37 to 40 settled in S5). 20.64 spent, 9.36 left. Unused S5 allocation still goes to S6 (IV.3). |
| S8 sealed evaluation | 60.00 | A new preregistration version is still allowed (no holdout sample drawn, no sealed result), so S4e item 2's sizing rule is re-run with 60 USD (D-S12 item 5, D-090). Reserve pays only infrastructure re-runs in S8. |
| Smoke runs (S12 item 8) | 3.00 | |
| Reserve | 7.00 | Storage share is charged here first. Unused allocation rolls forward. |

The reaper's hard stop is 99 USD and the guard counts against 100 USD, both read from the ledger's latest budget line (no figure in code, D-S9 item 3). Proven on the mocked provider (`tools/loop/reaper_proof.py` step 6, extended to a 49, 69, 99 chain: spend 69.1 leaves the instance alone, 99.1 terminates it), with neutralise (stop clamped to 69 in `budget_figures`), fail (step 6 false), restore, pass (D-090). Usage limits unchanged: no launch at five-hour 70 percent or seven-day 95 percent.

## Budget from 2026-10-29 21:26 UTC (operator decision D-S12 as revised at 00:20 +03:00; supersedes the 100 USD section above)

| Date (UTC) | Event | Instance minutes | Instance cost (USD) | Storage share to date (USD) | Total spent (USD) | Remaining (USD) |
|---|---|---|---|---|---|---|
| 2026-10-29 21:26 | Budget raised to 200 USD by the operator (D-S12 revised 00:20, replacing the 00:10 version applied at 21:10); reaper hard stop 199 USD; `budget_change` line appended at 21:26:33 UTC; the reaper's `budget_figures` reads (200.0, 199.0). No instance running. | 0 | 20.64 (S5 so far) | 0.35 (S5 closing reading) | 20.99 | 179.01 |

The allocation of D-S12 item 4 (S5's brought-back work and the first sweep's findings, then S6, S9, S10 and smoke runs, a 10 USD reserve, S8 the rest and never less than 60 USD) is computed after the first sweep and recorded here in its own table. The 100 USD table above is void. Reaper proof (`tools/loop/reaper_proof.py` step 6): the chain is now 49, 69, 199; spend 69.1 leaves the instance alone, 199.1 terminates it; neutralised (stop clamped to 99 in `budget_figures`) step 6 fails; restored, it passes (D-091).

### Allocation from 2026-10-30 about 00:50 +0300 (D-S12 item 4, D-092)

| Allocation | USD | Forecast basis |
|---|---|---|
| Spent to date | 20.99 | instances 20.64 (S5 launches), storage share 0.35 |
| S5 brought-back work and the first sweep's findings | 70.81 | L7 4.05, L8 15.12, L9a and L9b 24.65, CUAD one contract 21.76, dry runs 5.22 (2,533.5 instance minutes at 0.02795 USD a minute, exposed-batch overhead 15.4 minutes a session and 2 an entry) |
| S6 cloud work | 5.74 | GNN graph 1.70, report-optimized measurement 0.64, S6b re-score 1.70, open item runs 1.70 |
| S9, S10 | 0.00 | no Lambda work named |
| Smoke runs (S12 item 8) | 3.12 | two smoke runs with the upload |
| Reserve | 10.00 | storage share charged here first (about 0.65 USD more to S5's end, estimate) |
| S8 sealed evaluation | 89.34 | the rest; floor 60 |

CUAD forecast basis (D-094, closing the version 2 attack's item 8): one development contract at the mean of the 8 measured B2 contracts, 2,643 judging plans (SELECTION.md), at 17.0 seconds a plan everything included (L6, ContractNLI band B: 81.8 minutes over 289 plans), 748.9 minutes of B3; B1 tuned on its 41 items at about 15 seconds a call, 10.3 minutes; 15.4 minutes of session overhead and 2 minutes an entry for each arm: 778.6 minutes, 21.76 USD. A band B contract (about 1,230 plans, an estimate) would be 378.2 minutes, 10.57 USD. The contract is chosen at launch from the B2 plan counts; the forecast stays the mean's, so S8's fixed A (89.34 USD) does not depend on that choice.

### Launches after D-S12 (forecast against actual)

| Run | Purpose | Forecast basis | Forecast (USD) | Cap (USD) | Billed minutes, notes | Actual (USD) |
|---|---|---|---|---|---|---|
| L11 (2026-10-29 23:18 to 2026-10-30 02:29 UTC, D-097) | dev-dryrun-l11, 8 development documents B3 + B1 tuned, sealed at d50b299 | 198 minutes (staging lane's point forecast), A10 1.29 USD an hour, times 1.3 | 5.53 | 8.30 | 191 (ledger); 16 entries; every B3 entry reached its end; six B3 entries semantically incomplete (`semantic_incomplete`, pipeline exit 0); MATCH | 4.11 (ledger). Variance: actual 74 percent of forecast |
| L7 (2026-10-30 02:57 to 04:01 UTC, D-097) | dev-multiround-l7, 12 entries b3_only (two multi-round cases, catalogue regression, two negotiation comparisons, seven family-4 tests and twins multi-round), sealed at 55f1dd1 | 380 minutes (multi-round at about 13 minutes a round), times 1.3 | 10.62 | 15.93 | 64 (ledger); the nine multi-round entries reached `reviewed` with no model call in seconds each and were failed by the runner's model-call requirement (`required_telemetry_missing`, D-100); catalogue completed; both negotiation comparisons semantically incomplete; MATCH | 1.38 (ledger). Variance: actual 13 percent of forecast (the multi-round phase now asks no model) |
| L10 (2026-10-30 04:08 to 06:13 UTC, D-097) | dev-cuad-l10, CUAD development contract 527255a5c970, B3 + B1 tuned, sealed at 55f1dd1 | 147 minutes (410 plans at 17 seconds, B1 41 calls), times 1.3 | 4.11 | 6.16 | 125 (ledger); B3 semantically incomplete, 410 uncomputable judging calls all refused under D-068; B1 completed; MATCH | 2.69 (ledger). Variance: actual 65 percent of forecast; the allocation had forecast 21.76 USD for CUAD at the 2,643-plan mean (D-092, D-097) |
| L8 (2026-10-30 07:41 to 12:12 UTC, D-097) | dev-suite-l8, 20 development-suite tests and twins, B3 then B1 tuned (40 entries), sealed at 55f1dd1 | 540 minutes (15.4 + 20 x 15.2 + 20 x (9 + 2)), times 1.3 | 15.09 | 22.64 | 271 (ledger); usage at launch five-hour 4, seven-day 37; disk 39 GB; B1 20 of 20 passed; B3 1 of 20 passed and 19 failed: 12 did not complete (10 with `backend_failure`, one of them also `required_contract_failure`; 2 with `required_telemetry_missing`), 7 `semantic_incomplete` (4 of them also `required_contract_failure`); the reasons do not overlap across the two groups (s5_diag_b3); diagnosis under D-S14 (D-111); MATCH | 5.83 (ledger). Variance: actual 39 percent of forecast |
| R1 (2026-10-30 13:27 to 15:02 UTC, ledger, D-114, D-116) | d-s14-constraint-replay, one exposed replay-only B1 bundle, 136 producer prompts on two paths, sealed at cd498a3 | 112 minutes, times 1.3 | 3.13 | 4.70 | 96 (ledger); usage at launch five-hour 24, seven-day 44; disk 33 GB; rules A to D met, 52 of 52 failing partitions valid under the constraint; MATCH | 2.06 (ledger). Variance: 66 percent of forecast |
| L12 (2026-10-30 16:26 to 2026-10-31 02:36 UTC, ledger; D-S14, D-115) | dev-rerun-l12, the 37 development B3 entries of L7, L8, L10 and L11 that did not pass, after the D-S14 fixes, sealed at 2b585af | 500 minutes (D-115), times 1.3 | 13.98 | 20.96 | 610 (ledger); usage at launch five-hour 7, seven-day 47; disk 76 GB; 24 of 37 passed (L7 11 of 11, L11 5 of 6, L8 8 of 19, L10 0 of 1); the 13 others semantically incomplete with a required contract failure (PRACTICE_AUDITOR 9, VERIFIER 8, ARCHIVIST 1 violations; none from the producer); MATCH | 13.12 (ledger). Variance: 94 percent of forecast |

Usage at each launch since D-S12 (status line, five-hour and seven-day percent; D-107): L11 0 and 35 (2026-10-29 23:17 UTC), L7 2 and 36 (02:56 UTC), L10 0 and 36 (about 04:08 UTC), L8 4 and 37 (about 07:40 UTC). Free disk before each: L11 36 GB, L7 32 GB, L10 42 GB, L8 39 GB. The allocation table above was written at 00:39 (D-092), not "about 00:50".

### Running total (2026-10-30 09:22 UTC, D-107)

| Date (UTC) | Event | Instance cost to date (USD) | Total spent, reaper (USD) | Remaining (USD) |
|---|---|---|---|---|
| 2026-10-30 09:22 | After L11 (4.11), L7 (1.38) and L10 (2.69); L8 running. Reaper reading 09:21:59 UTC: one loop instance listed, total spend 31.40 (it counts L8 to its reading time and the storage share). | 28.82 (S5 20.64 plus 8.18) | 31.40 | 168.60 |

### S5 re-forecast after D-097 (D-107)

S5's brought-back allocation was 70.81 USD. Spent on it so far 8.18 (L11, L7, L10). Forecast for the rest: L8 15.09, L9a (37 entries: 28 probes at 15.2 minutes plus 9 multi-round re-runs at about 2 minutes, 15.4 overhead, about 459 minutes) 12.83, L9b 12.33. Total about 48.4 USD, 22.4 USD under the allocation; the difference rolls forward to work a later sweep brings back (D-S12 item 4), never to S8, whose A is fixed by version 2. L11 was sealed at `d50b299`, before the measurement merge, a departure from D-097 (e) recorded in D-102.

### Allocation redone for D-S13 and D-S14 (D-115)

| Allocation | USD | Forecast basis |
|---|---|---|
| Spent to date | about 35.2 | instances 34.65 (S5 20.64; L11 4.11, L7 1.38, L10 2.69, L8 5.83), storage about 0.5 |
| S5 remaining | about 68.1 | R1 3.10; L12 re-run of 37 entries 13.98; L9a 12.83; L9b 12.33; L13 FinDVer and CUAD-claim development 19.4; launcher review and draft 1.5; second re-run margin 5.0 |
| S6 cloud work | 5.74 | as D-092, the GNN run included |
| Smoke runs | 3.12 | |
| Reserve | 10.00 | storage first |
| S8 | about 77.8 | the rest; floor 60; version 3 is sized from the ledger when written |

### Running total and corrections (2026-10-30 20:4x +0300, D-121)

| Date (UTC) | Event | Instance cost to date (USD) | Total spent, reaper (USD) | Remaining (USD) |
|---|---|---|---|---|
| 2026-10-30 17:26 | After L8 (5.83) and R1 (2.06); L12 running. Reaper reading 17:26:59 UTC: one loop instance listed. Instances by the ledger's terminations: 36.70 (36.7005: S5 before D-S12 20.64, L11 4.11, L7 1.38, L10 2.69, L8 5.83, R1 2.06) | 36.70 | see reaper_status.json at the reading (it counts L12 to that time and storage) | about 162.8 before L12 |

Corrections: R1's forecast is 3.13 USD (112 minutes at 1.29 USD an hour, times 1.3; the ledger's 3.1304), not 3.10; D-115's S5 remaining becomes about 68.2. L9a holds the 28 probes only (the nine multi-round re-runs are in L12, D-112), so its forecast is 441 minutes, 12.33 USD, not 12.83; D-115's S5 remaining becomes about 67.7. Launch times in the rows above are the ledger's launch lines.

### Running total after L12, and R2's forecasts (2026-10-31 11:04 +0300, D-130)

| Date (UTC) | Event | Instance cost to date (USD) | Total spent, reaper (USD) | Remaining (USD) |
|---|---|---|---|---|
| 2026-10-31 06:16 | After L12 (13.12). Reaper reading 06:16:59 UTC: 0 instances. Instances by the ledger's terminations: 49.82 (49.8155: S5 before D-S12 20.64, L11 4.11, L7 1.38, L10 2.69, L8 5.83, R1 2.06, L12 13.12) | 49.82 | 50.35 | about 149.6 |

| Launch | Purpose | Forecast minutes | Bundle |
|---|---|---|---|
| R2a | d-s14-envelope-replay-auditor, 82 prompts, sdpa and sdpa_constrained | 130 | external/s05/R2/auditor_B1 (sealed at 7cb979e) |
| R2b | d-s14-envelope-replay-archivist, 14 prompts, sdpa and sdpa_constrained | 40 | external/s05/R2/archivist_B1_abd (sealed at abd288c; `archivist_B1`, sealed at 7cb979e, was never launched) |
| R2c | d-s14-verifier-cap-4096, 8 prompts, sdpa_constrained, informational | 75 | external/s05/R2/verifier_cap_B1_abd (sealed at abd288c; `verifier_cap_B1`, sealed at 7cb979e, was never launched) |

The smoke 3.12 of the allocation table above went back to the pool under D-S17 item 3 (D-127); it is not spent on S12.

| Launch | Window (UTC, ledger) | Forecast (USD, cap) | Actual |
|---|---|---|---|
| R2a | 2026-10-31 08:05 to 10:10, d-s14-envelope-replay-auditor, sealed at 7cb979e | 3.63, cap 5.45 (130 minutes times 1.3) | 125 minutes, 2.69 USD; integrity passed, 164 reply records; A, B, C hold, 12 of 22 fixed (D-132). Usage at launch not read; disk 69 GB, free memory 4.2 GB. Instance total after it: 52.50 |
| R2c | 2026-10-31 10:20:59 to 11:30:14, d-s14-verifier-cap-4096, sealed at abd288c | 2.10, cap 3.14 | 70 minutes, 1.51 USD; integrity passed; 4 of 8 end within 4,096 (D-134). First two-instance use (D-133); free memory 3.47 GB, disk 69 GB at launch |
| R2b | 2026-10-31 10:21:37 to 10:48:48, d-s14-envelope-replay-archivist, sealed at abd288c | 1.12, cap 1.68 | 28 minutes, 0.60 USD; integrity passed; A to D hold, 2 of 2 fixed (D-134) |

### Running total after R2, and the allocation under D-S18 (2026-10-31 15:40 +0300, D-133, D-135)

| Date (UTC) | Event | Instance cost to date (USD) | Total spent, reaper (USD) | Remaining (USD) |
|---|---|---|---|---|
| 2026-10-31 11:46 | After R2a, R2b, R2c. Reaper reading 11:46:59 UTC: 0 instances. 18 terminations | 54.61 | 55.18 | about 143.8 under the 199 hard stop |

| Allocation (D-S18 item 7 order) | USD | Forecast basis |
|---|---|---|
| v1 work left | about 9.0 | L12b 13 entries, about 310 minutes in two sessions, about 6.5 with the 1.3 factor plus margin; L14 launcher review and draft 1.5; slack 1 |
| Parallel track (D-S18 item 6a) | 30.00 | requests in `docs/loop/private/parallel/`, refused past this |
| Sealed evaluation (version 3, ContractNLI and SciTab, D-S18 item 5) | at least 60 | floor 60; sized from the ledger when version 3 is written |
| Moved steps (D-S18 item 3) | about 42 | L13 about 17.4, L9a 12.3, L9b 12.3; S6 cloud work 5.74 is inside the sealed evaluation's surplus or waits |
| Total | about 141 | of about 143.8 left; if a forecast grows, L9b waits first and FOR_SECKIN says so |
