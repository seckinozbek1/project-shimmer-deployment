# On a rented cloud machine (the console's cloud mode)

Turkish name: Kiralık bulut makinesinde. D-S49 item 3, D-S50 item 3, D-S51 step 3(e), D-S62 item 9.

From the console the user runs a real review on a rented machine that is started for the run and
shut down after it. Every screen says, in one sentence, where the documents go:

- "Your documents are copied to the rented machine for this review and deleted with it when it is
  shut down."
- "Belgeleriniz bu inceleme için kiralık makineye kopyalanır ve makine kapatılınca onunla birlikte
  silinir."

## What it goes through

Nothing goes around the sealed, bound path (CLAUDE.md LOOP-LAUNCH-A, CONTROLLER-BINDING). The
server (`scripts/server.py`, routes `/cloud...`, logic in `scripts/console_cloud.py`) runs, as
hidden child processes, the tools every loop launch uses:

1. stage the chosen files as a workload folder (`context/`, `conventions/`,
   `_review_targets.json` with `source: operator`), the layout `tools/stage_workload.py` writes;
2. read the provider inventory (`tools/console_cloud_inventory.py`: the three read-only requests
   the bound live preflight makes);
3. seal an exposed B3 bundle (`tools/prepare_ordinary_final_run.py --exposure exposed --arm B3
   --reuse-assets ... --ledger <private ledger> --forecast-minutes ... --storage-forecast-usd ...`);
4. verify the asset archive (`tools/verify_ordinary_final_assets.py`);
5. write `authorization_binding.json` from the bundle's own digests;
6. reverify locally (`tools/ordinary_final_bound_reverify.py`);
7. declare the asset copy (`tools/declare_asset_copy.py`) only when the operator's settings name
   one;
8. the live preflight (`tools/ordinary_final_bound_preflight.py`).

Nothing in these steps spends money. The launch is a separate request. It runs
`tools/ordinary_final_bound_cloud.py --bundle ... --output-dir output/cloud/<plan id>/run --ledger
<private ledger> --purpose console-<plan id> --forecast-minutes ... --storage-forecast-usd ...
[--forecast-includes-upload] --detach`. The guard, the ledger lines, the deadline, the watchdog and
the reaper then act as they do for every loop launch. The detached controller does
not depend on the server: closing the console does not stop the machine's own shutdown. No bound
controller file was changed for this mode, so no bundle needs to be sealed again because of it.

## What the user confirms before any spend

The plan screen shows the following, all read from the seal:

- the forecast time and cost;
- the cap, which is the most the run can cost;
- the machine type and its hourly price;
- whether the model upload is in the forecast.

It also says whether the forecast is MEASURED (with its date and machine) or an ESTIMATE (with
what the estimate rests on), as `config/cloud_forecast_basis.json` records. The shipped basis is
an estimate until a console run is measured (D-S51 step 5). A new decision then replaces it with
the measured entry.

To start, the user asks for a confirmation code, reads "This starts a rented machine that costs
up to X USD. It is shut down after the review.", and types the amount back. The launch is
refused unless:

- the amount equals the cap shown, to the cent (rounded up, so "up to" is never below the sealed
  cap);
- the code is this plan's code;
- the code is unused, since a code is spent on its first use, whatever the outcome;
- the code is under 15 minutes old.

Codes live only in the server process.

## What the console never does

- It never asks for, reads, holds or shows the provider key. It only asks
  `agent_wrapper.resolve_config_path()` whether a credential file can be found, and answers yes
  or no. With none found it refuses: "set SHIMMER_CONFIG_PATH to your own credential file outside
  the repository". The file is read only by the provider adapter inside the child processes.
- It never writes, opens or changes a budget line. With no `budget_open` line it refuses.
- It never prepares or launches a sealed run.
- It shows no instance limit: there is none (D-S95). The machines running are counted, and the
  total budget and its hard stop are the only limit.

## While it runs and after

While the run is preparing, the console shows the steps done out of the total, and how long the
current step has been running. Each step reports only on completion, and the console says so.

While the run is on the machine, the progress line is `tools/ordinary_final_progress.py`'s own
reading of the run folder (PROGRESS-A): measured, or "not measurable" with the reason.

At the end, the console shows:

- the actual minutes and cost, from the ledger's termination line, beside the controller's upper
  bound (the provider invoice may differ);
- the minutes for each part, from the controller's timing receipts: starting the machine, copying
  files, preparing the machine, the review, collecting results and shutting down. Model loading
  happens inside the review and is not timed apart;
- whether the machine was shut down. That needs both the provider's `terminated` status and the
  controller's cleanup finding its own instance gone. If either is missing, the console says the
  shutdown is not confirmed.
- with the shutdown confirmed, "The rented machine and its copy of your documents are gone." /
  "Kiralık makine ve belgelerinizin oradaki kopyası artık yok." (never without the confirmation);
- each document's deliverables, listed from the collected run
  (`<run folder>/downloaded/evidence/run/deliverables/`), each file and each document's zip downloaded
  through token routes (`GET /cloud/plans/{plan_id}/files/{doc_id}/{name}`, `_run` for the run's own
  files, and `GET /cloud/plans/{plan_id}/deliverables/{doc_id}`, the same zip helper as the run
  deliverables route). Only a listed name is served: the name is matched against the listing before
  any path is built. They are sibling routes because `/runs/{run_id}/deliverables` serves only the
  server's own jobs, and a cloud run is not one.

## The ledger and the loop's own launches

The bound wrapper accepts only a ledger the reaper reads, so a console launch writes the private
ledger (`docs/loop/private/budget_ledger.jsonl` in the user's own clone). The loop's launches stay
apart from the console's in two ways: each console launch carries the purpose `console-<plan id>`,
and each runs in its own folder under `output/cloud/<plan id>/`. Both kinds share one budget and one
reaper on purpose; there is no instance limit (D-S95). A third ledger would change `tools/loop_budget_guard.py`
and `tools/loop/instance_reaper.py`, which are bound files.

During the autonomous loop, step 5's launch from the console is a loop launch (D-S62 item 9). The
user-facing path with the user's own key is proved only after the loop ledger closes. The guide
says which of the two was proved.

## Operator setup (once, by hand)

Write `output/cloud/console_settings.json` (gitignored) with these fields:

```json
{
  "reuse_assets": "<a sealed bundle folder whose asset_verification.json passed>",
  "wheelhouse": "<the wheelhouse folder the asset verification reads>",
  "storage_forecast_usd": 0.5,
  "asset_copy": {"filesystem_name": "<the operator's filesystem>", "mount": "/lambda/nfs/<name>"}
}
```

`asset_copy` may be `null`. Without a copy the forecast includes the upload. The budget line is
the operator's, written in the ledger as for every loop launch. The sealer still requires a clean
working tree at the bound commit.

## Proofs

`scripts/console_cloud_checks.py` (gate check 338) proves the mode on fakes only. It makes no
network call and starts no instance, and every proof runs in a temporary folder. Each guarded
rule is neutralised in memory, the proof is shown to fail, and the restored rule is shown to
pass. `scripts/console_view_checks.py` (check 306) counts `scripts/console_cloud.py` among the
files whose every child process must be started without a window (HIDDEN-A).
