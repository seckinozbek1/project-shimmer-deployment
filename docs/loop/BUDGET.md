# Loop budget

The Lambda budget for this loop is 50 USD in total (Part II, H3), counted from the start of S0 (2026-10-27 03:16 UTC). This file shows the running total, the forecast against the actual cost of every run, and what remains. It never holds an instance id. The private ledger (`docs/loop/private/budget_ledger.jsonl`) holds the detail.

## Running total

| Date (UTC) | Event | Instance minutes | Instance cost (USD) | Storage share to date (USD) | Total spent (USD) | Remaining (USD) |
|---|---|---|---|---|---|---|
| 2026-10-27 03:16 | Budget opened at S0. No instance running, no orphan. | 0 | 0.00 | 0.00 | 0.00 | 50.00 |

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
