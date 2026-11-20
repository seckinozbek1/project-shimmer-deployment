# v1.05 first user interface: the review desk

Ships by 23 November 2026 23:59. Goal: a first interface that works, not one that looks professional.
Lane `lane/v105-ui`. Written 19 November 2026 (night). No pipeline run on this machine at any step.

## 1. What already exists (read before building anything)

| Surface | Where | What it does today |
|---|---|---|
| Operator console | `scripts/ui/console.html` (about 200 KB, vanilla JS, no build), served at `GET /console` | Upload and intake plan, submit, runs, findings, model findings, replies, switches, report, approvals, ontology, cloud mode. CONSOLE-A: sealed runs show counts only. |
| Front door | `scripts/server.py`, token-gated (SHA-256 of the token in `SHIMMER_TOKEN_HASH`), route table in `docs/RUNTIME_REFERENCE.md` (check 167 holds the table to the app) | `/submit` adds `--sensitivity-layer-inactive-override` and `--no-redaction-override` when the job's privacy is Normal (`sensitive=false`), runs `pipeline.py` as a subprocess, keeps the latest `[progress]` line on the job. |
| Desktop starter | `start_shimmer.bat` and `scripts/desktop_launcher.py` | Starts the server on loopback with a fresh token, copies the token to the clipboard, opens `/console`. |
| Terminal launcher | `shimmer.bat`, `shimmer.sh` (arm L source), `scripts/intake_wizard.py` | Menu, wizard, chat window. |
| Chat window | `scripts/chat.py` (tkinter) | Parses `[progress]` lines into a bar. |
| Cloud console | `scripts/console_cloud.py`, `scripts/ui/cloud_mode.js` (CLOUD-CONSOLE-A) | Sealed, bound path with typed cap and one-time code. Out of scope for v1.05. |
| Demo | `tools/build_demo.py`, `scripts/ui/demo.html` (DEMO-A) | Static, request-free, never served. Out of scope. |

So v1.05 does not need a new application. The console is large and covers far more than one review; a
newcomer gets lost in it. v1.05 adds one small page, the **review desk**, that walks one journey on the
server's own routes, plus the three read-only answers that journey needs and the console lacks.

## 2. The operator journey

1. **Open.** `start_shimmer.bat` as today (token on the clipboard). Open `/console?view=desk`, paste the token, Connect.
2. **See what is in place.** The desk lists `input/conventions`, `input/context` and `input/operational` (names, sizes;
   never content) and the compiled rules by id and the operator's own category (`GET /inputs`). Rule text is one
   click away (`GET /rules/{rule_id}`, existing).
3. **Choose inputs and conventions (step 2).** File picker; each file gets a role: review target, prior version,
   grounding, or conventions. Conventions already in `input/conventions` stay in force; uploaded convention files are
   detected by the wizard's parser as today; a differing file of the same name is refused by the server, never
   overwritten.
4. **Start a review (step 2).** Privacy Normal or Sensitive, shown with the server's own explanation
   (`/health` `sensitive_layer_active`). Normal sends `sensitive=false`, so the server adds both override flags exactly
   as it does for the console; Sensitive refuses (exit 6) while the LAW-IV layer ships inactive, and the desk says so
   before upload. The desk shows the plan and sends `/submit` with `intake_mode=standalone`, `confirmed=true`,
   `review_targets`, `prior_files`. No new start path: the launcher path is the server's `/submit`.
5. **Watch progress.** PROGRESS-A's four values every 5 seconds while the run is live (`GET /runs/{run_id}/progress`):
   documents done against the pipeline's own total, elapsed, rate, remaining at that rate. A value that cannot be
   measured is shown as "not measurable" with its reason, never estimated. The phase label is shown as the pipeline's
   nominal phase, not as a share of the work. Pending approvals and cancel use the existing POST routes (step 3).
6. **Read.** Per finished document, `reviewed_document.md` (READABLE-A) as text (`GET /runs/{run_id}/reviewed/{doc_id}`),
   then the typed findings (`/runs/{run_id}/findings`) and the model findings not promoted (`/runs/{run_id}/model-findings`).
   Downloads use the existing zips (`/runs/{run_id}/deliverables[/{doc_id}]`).
7. **Honest marks (HONEST-OUTPUT-A).** Every finding row says who wrote it (`written_by`, read off its bus post). Each
   model-written row carries the server's own `MODEL_FINDING_MARK` text ("Written by a model. Not promoted to an
   amendment. Not checked by Python."), taken from the `/model-findings` answer, never retyped in the page. An empty
   findings list says it does not certify a clean review.
8. **Sealed runs.** A run whose record says `exposure: sealed` is planned progress only: counts and timings, no
   document name, no findings, no reviewed document (the server refuses those with 403 in any case).

## 3. Routes

Existing routes the desk uses: `GET /health`, `GET /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/findings`,
`GET /runs/{run_id}/model-findings`, `GET /rules/{rule_id}`, `GET /runs/{run_id}/deliverables`,
`GET /runs/{run_id}/deliverables/{doc_id}`, `GET /runs/{run_id}/log`; step 2 and 3 add `POST /submit`,
`POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/approval`, `GET /approvals`.

New in step 1 (all read-only, all token-gated, projections in `scripts/review_desk.py`):

| Route | Answer |
|---|---|
| `GET /console?view=desk` | The page. Served by the existing ungated console shell route, so the set of routes with no token stays `/health` and `/console` (the launcher banners and their check name exactly that set; `shimmer.sh` is an arm L source and is not edited). Any other `view` is 404. |
| `GET /inputs` | Names, sizes and times of the files in the three input folders, capped at 500 per folder; compiled rules as id, category, severity. |
| `GET /runs/{run_id}/progress` | PROGRESS-A's four values with `not_measurable` reasons, the nominal phase note, and the one-line reading from the tracked reader `tools/ordinary_final_progress.count_reading` when the installation carries it. Counts and timings only, so a sealed run answers too. |
| `GET /runs/{run_id}/reviewed/{doc_id}` | `reviewed_document.md` as text. The name is matched against the run's deliverables listing before any path is built; 404 otherwise; 403 for a sealed run. |

No new route is needed for step 2: `/submit` already takes everything the start form sends.

## 4. Smallest build

One file `scripts/ui/desk.html` (plain HTML, inline CSS and vanilla JS, no CDN, no build tool, no storage: the token
lives only in the page's memory). Its view functions are pure (`DeskViews`: JSON in, escaped HTML out, and `plan(record)`
naming the routes it will call), so Node can run them in the gate. One module `scripts/review_desk.py` (stdlib only).
About 25 lines added to `scripts/server.py`. No file that tonight's v1.0 runs are bound to is touched:
`scripts/pipeline.py`, `cell_selection.py`, `orchestrator.py`, `paired_review.py`, the controller and runner files,
the launchers. Note: `scripts/server.py` is inside the source archive any later seal builds from its bound commit, so a
bundle sealed after this lane is merged carries it; bundles already sealed are bound to their own commits.

## 5. Proof

Check 620 (`scripts/review_desk_checks.py`; numbered 539 on lane/v105-ui, renumbered on lane/v105-ui-d2 because the
lead tip's negotiation check holds 539), all on fixtures in a temporary folder:

- A, always: the projections executed. Input listing names without content; four progress values equal to the
  hand-computed figures (1 of 3 documents, 10.0 min, 0.1 per min, 20.0 min) and an unstarted run gives a reason for each
  missing value; the reviewed document served by listing, unknown and escaping names refused. Neutralised (the listing
  match removed), an escaping name is served, so the proof fails; restored, it passes.
- B, with fastapi and node: the real app through FastAPI's test client, the server's `subprocess.Popen` replaced by a
  fake that fails the proof if anything starts a process. The page is served without a token, an unknown view is 404,
  the three routes are 401 without the token and 200 with it, a sealed run's reviewed document is 403.
- C, with B: the page's own `DeskViews` run in Node on B's real answers. A sealed run plans `/progress` only and names
  no document; the model mark sits on the model-written row alone; document text is escaped; every route the page plans
  for the exposed run then answers 200 through the test client.

Steps 2 and 3 (lane/v105-ui-d2) are proved by `scripts/review_desk_actions_checks.py`, on a server loaded into a
temporary root (`startup_submit_checks._isolated_server`) with its Popen replaced:

- Check 621 (group start): `DeskViews.startPlan` in Node refuses no target, a duplicate name, no privacy choice and
  Sensitive while the layer is inactive (the server also refuses that one, 409); `submitFields` gives nothing until
  confirmed; its fields and the files sent to `/submit` give 202, and the fake run starter sees both override flags,
  `--output-dir` on the run's own folder, `--mode standalone`, the targets and the earlier version. Neutralised (the
  privacy field dropped), `/submit` answers 400 and nothing starts; restored, it passes.
- Check 622 (group actions): fixture runs, one exposed and one sealed waiting for a decision, one queued. The exposed
  question is shown, the page's Approve body is recorded verbatim (202, then 409 for a second answer) and the page says
  recorded, not resumed; the queued run is cancelled through the page's planned route, nothing deleted; the log tail
  (40 lines, escaped) and the two zips answer 200, the running run's archive called partial; the sealed run's question
  is timings only and it plans no log or download. Neutralised (the sealed return taken out), the page plans a sealed
  log route the server refuses with 403; restored, it passes.

## 6. Steps, lanes and hours to 23 November

| Step | What | Lane | Hours | Done by |
|---|---|---|---|---|
| 1 | Read-only desk: page, `/inputs`, `/progress`, `/reviewed`, check 620 (539 before the renumbering) | L1 | 2 | 19 Nov 03:00 (done) |
| 2 | Start form: file roles, privacy, plan, `/submit`; check 621 for the submit path with Popen faked | L1 | 4 | 19 Nov (done, lane/v105-ui-d2) |
| 3 | Cancel, pending approvals and answer, log tail, zip downloads from the desk; check 622 | L1 | 2 | 19 Nov (done, lane/v105-ui-d2) |
| 4 | Fresh-eyes walk-through on a copy of a saved run under `output/runs/` (server pointed at the copy with `SHIMMER_OUTPUT_DIR`, no run); screenshots with the `tools/console_screenshots.py` pattern; fixes | L2 (independent reader) | 3 | 22 Nov |
| 5 | README newcomer section and RUNBOOK lines; the desk linked from the console's first screen | L1 | 1 | 22 Nov |
| 6 | Buffer for gate findings and merge after tonight's runs | lead | 2 | 23 Nov |

About 14 hours in all. L1 and L2 never run the gate on the laptop as a whole; they run their own check modules.

## 7. Open points

- Turkish strings for the desk: the console uses `scripts/ui/localization_catalog.js`; the desk is English only in
  v1.05.
- The desk polls every 5 seconds while a run is live; a long local run is fine at that rate.
- Checks 621 and 622 need fastapi and node and say they did not run without them.
- Check 620 needs fastapi and node for parts B and C. Where fastapi is absent (the laptop's `py -3.12`) part A alone
  runs and the result says B and C did not run; under the main checkout's `.venv` all three ran and passed.
