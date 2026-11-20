# v1.05 interface: the server trial on a rented machine (plan only)

v1.05 plan item D3, "Arayüz: çalışan sunucuda deneme" (`docs/loop/private/V105_PLAN_20261119.md` section 4), the
running-server part. Written 19 November 2026 on `lane/v105-ui-guide`. This is a plan: no folder is built, nothing
is sealed or launched, no server is started on the laptop (NO PIPELINE RUNS FROM THIS MACHINE; the laptop also has
no fastapi for `py -3.12`, memory note "gate environment baseline").

## 1. Why a rented machine, and which vehicle

The laptop never starts `scripts/server.py`. The existing interface checks (81, 104, 105, 109, 164, 167, 305, and the
desk's 620 to 622 on `lane/v105-ui-d2`) drive the app in-process through FastAPI's test client with the run starter
faked; none of them talks to a real uvicorn process over a socket. The trial adds that one missing proof: the server
started as the operator starts it (`python scripts/server.py`), asked over HTTP.

The vehicle is arm G (GATE-ARM-A), the sealed path every Lambda gate uses: `tools/prepare_ordinary_final_run.py --arm
G --gate-form full --gate-checks <list>` seals the bound commit's tracked tree, the instance makes it a git checkout
of that tree and runs `scripts/verify_session1.py --results <file> --checks <list>` in a child process with the
sealed model cache and the hub offline. The pattern to copy is `external/s05/ROUTE_GATE_174_340/` (16 November: a
route S seal job, admission, one gate part with two checks). No new arm, no bound controller file changed, so no
re-seal is caused by the trial itself.

## 2. What has to be built first (by a lane, not now)

1. `scripts/server_trial_checks.py`, registered in `scripts/verify_session1.py` CHECKS under the next free number at
   build time (called T below). Fixtures only, all in a temporary folder:
   - makes a token in memory and its SHA-256 hash; never prints, logs or writes the token;
   - builds fixture runs under a temporary `SHIMMER_OUTPUT_DIR` (one exposed finished run with a reference index,
     findings, model findings and `reviewed_document.md`; one sealed run waiting for a decision; one queued run),
     with the builders checks 620 to 622 already use; temporary copies for `SHIMMER_CONVENTION_REGISTRY`,
     `SHIMMER_AGENT_REGISTRY` and `SHIMMER_AGENT_HARNESS`;
   - starts `python scripts/server.py` as a child (HIDDEN-A flags through `cloud_run_common.no_window`) with
     `SHIMMER_HOST=127.0.0.1`, a free `SHIMMER_PORT`, `SHIMMER_TOKEN_HASH` and the paths above, no
     `SHIMMER_CONFIG_PATH` and no credential, waits for `/health`, and always stops it at the end;
   - asks it over HTTP with the standard library (no node, no browser), section 3;
   - each guard neutralised, failed, restored and passed, as every check does.
2. The trial folder `external/s05/V105_UI_SERVER_TRIAL/` (outside git), copied from `ROUTE_GATE_174_340`:
   `launch.py` (preflight, inventory, request, seal, admit, part, status, stop) with `COMMIT` the merged commit of
   section 5, `PURPOSES = {'seal': 'v105-ui-trial-seal', 'part': 'v105-ui-trial-part'}`, `FORECAST = {'seal': '20',
   'part': '24'}`; `requests.json` with one request, bundle `V105_UI_TRIAL`:
   `--arm G --gate-form full --gate-checks T,81,104,105,109,164,167,305,620,621,622 --forecast-minutes 24
   --storage-forecast-usd 0.5 --uncompared --instance-types gpu_1x_a10`; `chain.json` in the LAUNCH_CHAIN.md
   template (request, seal, admit, part, each after the one before, `watch` on the two ledger steps); and a
   `promise_watch.py add` line `v105:D3-server-trial` naming the folder and its output `evidence/result.json`.

## 3. What is checked

Against the real server process on the instance:

| # | Check | Pass when |
|---|---|---|
| 1 | Start refusal | `python scripts/server.py` with no `SHIMMER_TOKEN_HASH` exits 1 with its "Refusing to start" line and opens no port |
| 2 | Start | with the hash it answers `GET /health` 200 within the wait; under the local profile the start also needs `preflight.check_local_model_availability`, which the sealed model cache should satisfy: a refusal is recorded with its line and the remaining rows are not run |
| 3 | The two open routes | `GET /health` and `GET /console` answer 200 without a token; `/health` carries no `SHIMMER_` value, path or hash |
| 4 | The token gate | every other route of the table in `docs/RUNTIME_REFERENCE.md` (read from the file, as check 167 reads it, path parameters filled from the fixtures) answers 401 with no `Authorization` header, 401 with a malformed header and 401 with a wrong token |
| 5 | The routes answer | with the token, each GET route answers 200 for the exposed fixture run and 404 for an unknown run id; `/openapi.json`, `/docs`, `/docs/oauth2-redirect` and `/redoc` answer 404 |
| 6 | Sealed run | with the token, the sealed fixture run answers 403 on `/findings`, `/pairs`, `/amendments`, `/amendment-refusals`, `/contract-violations`, `/references`, both `/deliverables`, `/log`, `/undated-documents`, `/convention-assignment` and `POST /evidence`; `GET /runs/{id}` and `GET /approvals` carry counts and timings only (no document, file or target name, no question text) |
| 7 | Actions that start nothing | `POST /submit` with no privacy field answers 400, with `sensitive=true` 409 (layer inactive); `POST /runs/{id}/cancel` on the queued fixture run is accepted and deletes nothing; `POST /runs/{id}/approval` on a fixture run waiting for a decision 202, a second answer 409 |
| 8 | Cloud routes spend nothing | `GET /cloud` says no credential file found; `POST /cloud/plans` is refused for it; confirmation and launch on an unknown plan are refused |
| 9 | The desk (after the UI merge) | `GET /console?view=desk` 200 without a token, any other `view` 404; `/inputs`, `/runs/{id}/progress` and `/runs/{id}/reviewed/{doc_id}` 401 without and 200 with the token; the sealed run's reviewed document 403 |
| 10 | Nothing ran | after the rows, no new run folder in `SHIMMER_OUTPUT_DIR` and no `pipeline.py` child of the server process (read from `/proc`), and the server stops when asked |

The other checks in the list (81, 104, 105, 109, 164, 167, 305, 620, 621, 622) run beside T as the in-process cross
check on the same tree, so a difference between the test client and the real server shows as one check passing and
the other failing.

Known in advance: the A10 instance has no node (D-520, ENV-LAMBDA). Checks 620 to 622 then run their part A only and
say that parts B and C did not run; that is declared before the read, never counted as a pass of those parts.
Screenshots at 1280 and 390 px and the cold walk-through by a fresh checker (the rest of D3) need a browser and are
not part of this trial.

What is read back: `evidence/result.json` (one row per check: number, title, status, seconds) and the gate log,
counts and statuses only. The run is exposed (arm G is exposed only) and holds fixtures only, no operator document.

## 4. Cost forecast (tools/loop/step_cost.py)

Step files beside this plan, priced on 19 November 2026 from the provider inventory
`external/s05/ROUTE_GATE_e958ecc4/inputs/provider_inventory.json` (observed 15:25 UTC, gpu_1x_a10 at 1.29 USD an
hour). Both figures are the budget guard's own forecast (minutes / 60 x price x 1.3).

| Step | File | Basis | Without the measures | With them |
|---|---|---|---|---|
| Seal job (route S) | `v105_ui_server_trial/trial_seal.json` | 20 billed minutes, measured: ledger `route-gate-i-seal`, 16 Nov | 20.0 min, 0.56 USD | 0.56 USD |
| Gate part | `v105_ui_server_trial/trial_part.json` | boot 4, install and set-up 4.7, return 1: the 16 Nov part `G1116_174_340` (21 billed minutes, its phase receipts); upload 64 without the asset copy (D-298), 9.0 with it (that part's receipts); workload 5 minutes, an estimate (that part's two checks took 56 s; T starts one server and makes about 150 requests) | 78.7 min, 2.20 USD | 23.7 min, 0.66 USD |
| **Total** | | | **2.76 USD** | **1.22 USD** |

Each step and the total are under the 5 USD step pre-approval (D-708, D-749), so no question to Seckin is needed for
the money (D-807). Caps at 1.5 times each forecast: 0.84 and 0.99 USD. The 16 November measurement of the same shape
was 0.43 + 0.452 = 0.88 USD actual.

```
py -3.12 -X utf8 tools/loop/step_cost.py --step docs/loop/stages/v105_ui_server_trial/trial_seal.json
py -3.12 -X utf8 tools/loop/step_cost.py --step docs/loop/stages/v105_ui_server_trial/trial_part.json
```

## 5. What it waits on (the v1.05 merge order)

The trial tests the interface as it ships, so it is sealed from the commit that carries the merged interface, not
from a lane tip. In order:

1. **The trial check (section 2, item 1) is built** on a UI lane branched from `lane/v105-ui-d2`, its check proved on
   fixtures where fastapi is present (the main checkout's `.venv` or the instance; never the whole gate on the
   laptop). 0 USD.
2. **v1.0 ships** (`docs/loop/private/v105/V10_SHIPPED.flag`). `scripts/server.py` and `scripts/verify_session1.py`
   travel in any seal built from a bound commit (V105_UI_DESIGN.md section 4), so the desk's `server.py` edit does
   not merge into the line v1.0 freezes from before the ship (V105 plan section 0).
3. **E1: the four lanes merge onto the v1.0 tag through `lane/v105-integ`**, merge base first, with the UI lanes
   (`lane/v105-ui`, then `lane/v105-ui-d2`, then the trial check's lane) among them; their check numbers are
   renumbered there if another lane took them (as 539 became 620).
4. **The trial runs on the `lane/v105-integ` commit after E1**, beside E2 (the grouped re-seal) and before or beside
   E3 (the v1.05 gate on arm G), on its own A10 (PARALLEL-LAMBDA-A). It needs no re-seal of its own beyond its seal
   job, and E2's re-seal is not needed for it.
5. **Its result feeds D4 and E4**: a red row is fixed on the integration branch and the trial repeated (about 1.22 USD
   each); a green trial is cited in the release notes as "the server answered every route on a rented machine,
   fixtures only".

An earlier run on the UI lane's own commit before v1.0 ships (same folder, `COMMIT` the lane tip) would find defects
two days sooner for the same 1.22 USD; it is the lead's choice within the limits (D-807) and does not replace the
run on the merged commit.

## 6. Not in this trial

A real review started from the interface (that needs the models and a pipeline run: the optional end-to-end proof
of the V105 plan, about 3.6 USD, basis L14d), the cloud mode's real launch (CLOUD-CONSOLE-A: proven on fakes only),
screenshots, and any operator document.
