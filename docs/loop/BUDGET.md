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
