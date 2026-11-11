# S7 plan: console UI and launchers

Drafted 2026-10-29 (system clock, +03:00). Branch `loop/s07`, created from the loop branch at `ea1c0d5` (S2 merged and tagged, S7's only dependency; Part V table). This is S7's first pass, run alongside S5 (Part V, IV.5). Its final pass runs after S6 merges: the loop branch is then merged into `loop/s07` in a commit of its own (IV.1), and the views are brought up to date with what S5 and S6 added. Opus, medium effort from 28 October 2026 (Annex D, D-S11).

## Start of stage

1. Open items read (`docs/fix/OPEN_ITEMS.md` at `ea1c0d5`). Those touching S7: none names the console directly; item 23 (nothing hands a sealed run's folder to the scorer) bears on spec item 2 and is not changed here.
2. Read-only trace done before this plan (a subagent, 2026-10-29): one page `scripts/ui/console.html`, 31 routes in `scripts/server.py` all in the route table, check 104 tests only 11 fixed routes, the S1 to S6 data mostly without a route or view, `py -3.12` lacks fastapi and uvicorn (the loop venv `<USER_HOME>/local/shimmer-fresh-clone/venv_gate312` has them), Playwright with Chromium available in `py -3.12`, two ways a sealed per-flaw breakdown could be reached today (`POST /runs/{id}/evidence`; `SHIMMER_OUTPUT_DIR` pointed at a sealed run's folder).
3. Plan check by a fresh `loop-checker` (I.3 step 5).

## Lanes (IV.5)

| Lane | Branch, worktree | Items | Files it owns |
|---|---|---|---|
| UI | `lane/s07-ui`, `.claude/worktrees/s07-ui`, from `loop/s07` | 1, 2, 3, 4 | `scripts/ui/console.html`, `scripts/ui/localization_catalog.js` (Turkish rows for new labels), `scripts/server.py`, a new `scripts/console_view_checks.py`, `scripts/verify_session1.py` (registration of new checks only), a synthetic fixture run folder under `scripts/fixtures/console/` (no real names, no benchmark data, exposed), `docs/loop/ui/` screenshots |
| Launchers | `lane/s07-launch`, `.claude/worktrees/s07-launch` | 5 | `shimmer.bat`, `shimmer.sh`, `start_shimmer.bat`, `scripts/desktop_launcher.py`, `tools/resolve_python.bat`, a new `scripts/launcher_checks.py` |
| Lead | `loop/s07` | merges, gate, records | `README.md`, `CLAUDE.md`, `docs/RUNTIME_REFERENCE.md` (route rows and prose), `CHANGELOG.md`, `docs/loop/*` |

The two lanes share no file. A new check is registered in `scripts/verify_session1.py` by the UI lane only; the launchers lane hands its registration line to the lead in its report. Merge order: UI, then launchers.

## Items

### 1. The console shows every S1 to S6 feature (UI lane)

Each view reads one new or existing read-only route; every new route returns 401 without a token. Data sources and routes:

| Feature (spec) | Data in a run folder | Route (new unless noted) | View |
|---|---|---|---|
| Saved model replies and outcomes | `audit/model_replies/*.json`, `outcomes.jsonl` | `GET /runs/{id}/replies`: per call: sequence, agent, model id, mode, call id, outcome, sizes; never the reply or payload text (a redaction run holds hashes only; the console never becomes a second copy of the text) | run detail, "Model replies" section with counts by outcome |
| Unpromoted model findings, marked | `deliverables/<doc>/review_data.json` `model_findings_not_promoted` | `GET /runs/{id}/model-findings` | a section that prints `finding_record.MODEL_FINDING_MARK` on every item, in both languages |
| Provenance labels | `written_by` on `/findings` (existing) | existing | kept; the producer sentence shown from `findings_provenance` |
| Multi-round runs and rounds | `audit/multi_round.json` (existing), `audit/round_reuse.json` | `/multi-round` (existing) gains the reuse record | rounds table with reused and recomputed units |
| INST_FINDER setting and ratification | `audit/agent_switches.json` | `GET /runs/{id}/switches` | "Agent switches": INST_FINDER on or off for this run, ratified or refused, with its reason |
| FACT_CHECKER withholding and reasons | `config/review_scope.json` `withheld_audit_agents`; the two Annex B.4 reasons | same route | the withholding and both reasons, from one source shared with `tools/analyze_ordinary_final_run.py` (the reasons move to one module both import; no second copy) |
| Purpose line, 11.12 report fields, cost and budget | a cloud session's `FINAL_STATUS.json` `report` rows and `run_record.json`; per-call `logs/cost_tracker.jsonl` and `audit/infrastructure_cost.jsonl` in a run folder | `GET /runs/{id}/report` (the report rows when the run folder carries them, else the run folder's own cost lines and "no cloud report for this run"); `GET /reports` lists cloud session reports from a folder the operator names, if any | "Run report" section; budget and cost per run where known, "not known" otherwise |
| Test-change request log | `docs/test_change_requests.md` (repository) | `GET /test-change-requests` (read-only, the file's entries as rows) | a read-only page |

Where a server setting is needed (the cloud reports folder), it is named by the lane after reading gate check 116's rule (T5): a variable that check 116 cannot accept is not added; the route then reads the run folder only.

### 2. Never a sealed test's per-flaw results (UI lane)

- A run whose record says `exposure: sealed` shows counts and timings only on every new view (Annex B.8): no finding text, no unit id, no rule id, no reason; the report view drops the recall, attribution and per-flaw rows.
- `POST /runs/{id}/evidence` refuses a sealed run (it would classify misses against supplied key entries).
- No route reads a scorer output, an answer key or `benchmark/`.
- A gate check proves each point on a synthetic sealed fixture (neutralise, fail, restore, pass).

### 3. API and gate checks (UI lane, lead for the table)

- Every new route gets a row in `docs/RUNTIME_REFERENCE.md`'s route table (check 167), written by the lead in the merge from the lane's report.
- A new check walks `app.routes` and requires 401 without a token for every route except `/health` and `/console` (the trace found check 104 covers 11 fixed routes; check 104 itself is not edited, H9 and IV.6: a new, stronger check is added beside it).
- One check per new view and route, run with a TestClient on the synthetic fixture: the route's fields, the mark on every model finding, the sealed filter. Checks 258 to 260 stay green. Each new check: neutralise, fail, restore, pass.
- Checks that need fastapi skip with a reason under `py -3.12` (as 104, 167 and 259 do today) and run in the loop venv; the proofs are run in the loop venv and recorded.

### 4. Screenshots (UI lane), then a checker

Serve the console from the loop venv on the synthetic fixture (exposed, no real names), render every changed view with Playwright (Chromium, `py -3.12`) at 1280 and 390 pixels wide, save PNGs under `docs/loop/ui/`. Before committing: look at each image for personal paths, real names, the collaborator's name and secrets, and run the H5 pattern and the private patterns over the rendered text (counts only). A shot that shows any of these is not committed and is recorded. Then a fresh `loop-checker` reviews the shots against the fixture's data for accuracy and for any line a reader could mistake for a verified finding.

### 5. Launchers (launchers lane)

Drive `shimmer.bat` (through `cmd /c` with piped input ending in `Q`), `shimmer.sh` (Git Bash) and `start_shimmer.bat` (`--check-entry`, `--no-browser`) as far as a script can, with no full run and no install (the menus' install step is skipped with what the scripts already offer, or recorded as needing a human): the review path to the point where it would start a run, the console path (option 3) to the server's start, on development fixtures. Fix what fails (known: the menus loop forever at end of input; the banner calls `/health` the only open route while `/console` is open too; `start_shimmer.bat`'s unused label). Each fix gets a check in `scripts/launcher_checks.py` where a check can hold it. List exactly what still needs a human in `FOR_SECKIN.md`.

## Gate and records

- The gate runs once per lane merge on `loop/s07` (chunked, as recorded in LOOP_STATE), compared with the main-checkout baseline; the server checks run in the loop venv as in S4 (D-054).
- No `scripts/pipeline.py` function changes, so no pinned-baseline amendment is expected; if one is needed it goes through IV.7.
- Three checkers at the close (IV.4); the final pass after S6 repeats the checks on the merged result.

## Exit criteria (spec) and evidence

| Criterion | Evidence |
|---|---|
| Console and launchers current, including S6's additions | views and routes per item 1; launcher fixes; final pass after S6 merges |
| Route table and checks 104 and 167 pass | gate in the loop venv; the new all-routes 401 check |
| Screenshots checked and reviewed | `docs/loop/ui/*.png`; the checker's report |
| Gate checks | new checks with neutralise, fail, restore, pass |
| Checkers closed; stage merged; tag | three checkers; merge; `loop-s07-v1` |

## Decisions this plan needs (III.2)

- **DS7-1** Replies view shows metadata and outcomes, never text (P7, H10: the console must not become a second store of reply text). Class R.
- **DS7-2** A new all-routes 401 check beside check 104 rather than editing 104. Class R (a gate change that strengthens; attacked by the stage's adversarial reviewer).
- **DS7-3** The B.4 reasons move to one shared module. Class R.
- **DS7-4** The sealed filter on every new view and the refusal of `/evidence` for a sealed run. Class R, touching evaluation integrity: attacked by the adversarial reviewer.

## Plan check 1 closures (2026-10-29, 13 items)

1. **Fixture replies.** `**/audit/model_replies/` is ignored and refused by `guard_secrets.py --staged`. The committed fixture holds no `model_replies` path; the checks and the screenshot server build that part in a temporary folder at run time. No `model_replies` path is ever staged.
2. **Which marker the sealed filter reads.** A pipeline run folder carries no exposure field today. The server reads, in order: `run_record.json` or `seal.json` in the run folder or in its parent session folders up to three levels (the cloud layout `<session>/downloaded/evidence/run`), `exposure` field; a run whose marker says `sealed`, or whose folder sits under any folder holding a `seal.json` with `exposure: sealed`, is sealed. A missing marker means exposed only when no `seal.json` is found on that path; the `SHIMMER_OUTPUT_DIR` case is covered because the walk starts from the run folder wherever `RUNS_DIR` points. A check covers both layouts.
3. **The exempt set (DS7-5).** Exactly `/health` and `/console` answer without a token. `/console` is the page shell and holds no data; every data call it makes carries the token (existing design, `server.py` header, check 104's docstring); this reading of the spec's "every route except `/health`" is recorded as a decision. FastAPI's built-in `/openapi.json`, `/docs`, `/docs/oauth2-redirect` and `/redoc` are switched off (they describe every route without a token). The new check fails if any route outside the exempt set answers without a token, and fails if the exempt set grows.
4. **The shared reasons module.** The UI lane also owns `tools/analyze_ordinary_final_run.py` (import change only) and the new module `scripts/run_report_text.py` holding the Annex B.4 reasons; the import path is traced (`tools/ordinary_final_controller_checks.py` imports the analysis module), and the controller side gate `tools/ordinary_final_controller_gate.py` and `tools/cloud_run_checks.py` are in the lane's proofs.
5. **The image (T15).** A route that reads `docs/test_change_requests.md` answers "not present in this installation" when the file is absent; `scripts/launcher_checks.py` and any check reading the root launchers or that file skip with a reason when the file is absent.
6. **Code rules.** New code under `scripts/` follows checks 21 (no personal path; the loop venv path never appears in `scripts/`), 112 (`log_event` form, no content names), 118 (pinned imports), 120 and 121 (imports cleanly), and 242 (a new module-level regex alternating lowercase words is added to its known list with a verdict).
7. **Server variables (T5, check 116).** A new server variable gets a row in `docs/RUNTIME_REFERENCE.md`'s variables table, drafted by the lane in its report and applied by the lead in the merge.
8. **Waiting on S6 (IV.1).** The loop-branch merge into `loop/s07` after S6 is tagged is its own commit, recorded in the stage report; from then on the checkers diff against `git merge-base loop/2026-10-27 loop/s07`.
9. **Gate runs (IV.7).** One gate per commit on `loop/s07` that changes more than `docs/loop/` (each lane merge, each lead commit of README, CHANGELOG, RUNTIME_REFERENCE or CLAUDE.md, the loop-branch merge), with only that commit's changes in the tree, plus the loop-branch gate after the stage merge; a commit touching only `docs/loop/` cites the last result.
10. **Close-out records.** `VERSION` bumped by the lead (server code changes), the `VERSIONS.md` row, `CHANGELOG.md`, `S07_REPORT.md` (with "Opus, medium effort from 28 October 2026"), `LOOP_STATE.md`.
11. **Two lanes (DS7-6).** The spec gives console and launchers to one UI agent (IV.5). They are split into two lanes because they share no file and can run in parallel (P19, IV.5 "parallel where it helps"); Class R, recorded.
12. **Final pass.** After S6 merges, the launchers are walked again together with the views.
13. **Screenshot checker.** The checker receives the PNGs together with the fixture files they were rendered from.

## Revisions during the first pass (2026-10-29)

- **Lane table.** The UI row also owns `scripts/console_views.py` (the projections; a separate module because check 261 runs the multi-round route's source in a bare namespace), `scripts/run_report_text.py`, `tools/analyze_ordinary_final_run.py` (import only), `tools/console_screenshots.py` (the renderer) and `scripts/fixtures/console/session/`. Fix lane `lane/s07-fix1` closed the screenshot checker's four items.
- **DS7-7.** A sealed run's existing per-flaw routes (`/findings`, `/pairs`, `/amendments`, `/amendment-refusals`, `/contract-violations`, `/references`, both `/deliverables`, `/log`) answer 403, beside `POST /evidence`: spec item 2 says the console never shows a sealed test's per-flaw results, and these routes would. A `seal.json` with no exposure field reads as sealed (fails closed; pre-S2 seals carry no field). Class R, P18.
- **DS7-8.** The Annex B.4 reasons for withholding FACT_CHECKER are a standing, repository-wide agent policy that Annex B.4 requires in every run report, sealed runs included; they are not a test's per-flaw reasons, so the sealed switches view keeps them, and the sealed note names precisely what is withheld (finding text, unit ids, rule ids, the reasons given for findings, per-flaw results). Class R.
