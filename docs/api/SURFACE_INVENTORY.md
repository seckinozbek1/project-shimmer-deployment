> Historical design/audit record. Current implementation and endpoint names are in the [README](../../README.md#api-and-developer-entry-points) and [routing/UI audit](../fix/ROUTING_UI_AUDIT.md). Old route counts, success wording, write-only ontology claims and success-only findings visibility below are superseded. The console now reads findings/pairs for nonqueued runs, distinguishes process completion from review quality, and shows recorded activation evidence. Rule text is current-registry data, not a historical snapshot.

# Server surface inventory

This document describes `scripts/server.py` (1442 lines) and `scripts/ui/console.html`
(235 lines) exactly as they exist on disk today. It is a factual inventory, not a design
proposal: it contains no recommendations. Every claim below cites a `path:line`.

## Routes

There are 11 routes, all defined in `scripts/server.py`. This matches the count and set
in `README.md:1079-1089`.

### `POST /submit`

- Definition: `scripts/server.py:1005`
- Token: required (`dependencies=[Depends(verify_token)]`, `scripts/server.py:1005`)
- Status code on success: `202` (`scripts/server.py:1005`, `status_code=202`)
- Accepts (multipart form, `scripts/server.py:1006-1010`):
  - `files: List[UploadFile] = File(default=None)`
  - `task: Optional[str] = Form(default=None)`
  - `question: Optional[str] = Form(default=None)`
  - `sensitive: Optional[str] = Form(default=None)`
  - `review_mode: Optional[str] = Form(default=None)`
- Validation performed inside the handler (`scripts/server.py:1043-1122`):
  - `task` defaults to `TASK_DEFAULT` (env `SHIMMER_TASK`, default `"review"`), lowercased,
    and any value not in `("review", "draft")` is silently coerced to `"review"`
    (`scripts/server.py:1048-1050`).
  - `review_mode`, if given, must be one of `REVIEW_MODES = ("paired", "wide")`
    (`scripts/server.py:205`); an unrecognised value raises `400`
    (`scripts/server.py:1052-1059`).
  - `task == "draft"` with no `question` raises `400` (`scripts/server.py:1063-1064`).
  - `task == "review"` with no uploaded files raises `400` (`scripts/server.py:1065-1066`).
  - File count over `SHIMMER_MAX_UPLOAD_FILES` (default `50`) raises `400`
    (`scripts/server.py:1070-1073`).
  - Per-file size over `SHIMMER_MAX_UPLOAD_MB` (default `25` MB) raises `400`
    (`scripts/server.py:1084-1089`).
  - Cumulative upload size over `SHIMMER_MAX_UPLOAD_TOTAL_MB` (default `200` MB) raises
    `400` (`scripts/server.py:1091-1096`).
  - If any files were uploaded, they are validated as a group by running
    `corpus_ingest/validate_contract.py` as a subprocess; a non-zero return code raises
    `400` with the validator's combined stdout+stderr as `detail.report`
    (`scripts/server.py:1105-1117`).
  - Any other exception while staging raises `400` with `detail=f"could not accept
    upload: {e}"` (`scripts/server.py:1120-1122`).
- Returns (`scripts/server.py:1145-1146`), quoted:
  ```
  {"run_id": run_id, "status": "queued", "task": task, "sensitive": job_sensitive,
   "review_mode": job_review_mode, "files": names}
  ```
- Status codes: `202` (queued), `400` (validation failure, oversized/over-count upload,
  contract violation, or any other upload-staging exception).

### `GET /status/{run_id}`

- Definition: `scripts/server.py:1149`
- Token: required (`scripts/server.py:1149`)
- Accepts: path parameter `run_id: str`.
- Behavior (`scripts/server.py:1166-1174`):
  - `run_id` is checked against `_RUN_ID_RE = re.compile(r"^\d{8}_\d{6}__[0-9a-f]{6}$")`
    (`scripts/server.py:276`); a non-matching value raises `404` before any lookup
    (`scripts/server.py:1166-1167`).
  - An unknown (but well-formed) `run_id` raises `404` (`scripts/server.py:1170-1171`).
  - On a match, the in-memory job dict (copied) is returned, updated with the three live
    counters from `_review_progress` (`scripts/server.py:1172-1173`).
- The job dict's fields are `_STATUS_FIELDS` (`scripts/server.py:416-418`):
  ```
  ("run_id", "status", "task", "submitted_at", "started_at",
   "completed_at", "exit_code", "error", "progress", "files",
   "sensitive", "review_mode", "question")
  ```
  plus the three counters merged in from `_review_progress` (`scripts/server.py:975-999`):
  `pairs_planned`, `pairs_arithmetic_only` (an int, or `null` when `review_mode` is not
  `"paired"`, `scripts/server.py:994-996`), `model_calls`.
- Status codes: `200`, `404` (malformed or unknown `run_id`).

### `GET /findings/{run_id}`

- Definition: `scripts/server.py:1177`
- Token: required (`scripts/server.py:1177`)
- Accepts: path parameter `run_id: str`, validated by `_validated_run_dir`
  (`scripts/server.py:786-798`, `1191`), which raises `404` for a malformed `run_id`
  or a `run_id` with no run folder on disk.
- Returns (`scripts/server.py:1193`), quoted:
  ```
  {"run_id": run_id, "count": len(records), "findings": records}
  ```
  where each element of `records` is the object built by `_project_finding`
  (`scripts/server.py:801-832`), quoted field set:
  ```
  {"agent": agent, "doc_id": doc_id, "item_id": item.get("item_id"),
   "revision": item.get("revision"), "rule_id": ..., "source_rule_id": ...,
   "unit_id": ..., "relation": item.get("relation"),
   "record_verdict": item.get("record_verdict"), "value_a": ..., "unit_a": ...,
   "value_b": ..., "unit_b": ..., "source_refs": [str(r) for r in refs],
   "explanation": ..., "field_label": ..., "delta": item.get("delta"),
   "band_distance_change": item.get("band_distance_change"),
   "provenance": ...}
  ```
- A run with no findings yet is `200` with an empty `findings` list, not `404`
  (`scripts/server.py:1188-1190`).
- Superseded revisions (same `item_id`, lower `revision`) are removed before returning
  (`_bus_findings`, `scripts/server.py:835-889`).
- Status codes: `200`, `404` (malformed or unknown `run_id`).

### `GET /pairs/{run_id}`

- Definition: `scripts/server.py:1196`
- Token: required (`scripts/server.py:1196`)
- Accepts: path parameter `run_id: str`, validated by `_validated_run_dir`
  (`scripts/server.py:1205`), same `404` behavior as `/findings`.
- Returns (`scripts/server.py:1207`), quoted:
  ```
  {"run_id": run_id, "document_count": len(docs), "documents": docs}
  ```
  where each element of `docs` is built by `_pairs_view` (`scripts/server.py:904-941`),
  quoted field set:
  ```
  {"document_id": ..., "unit_count": ..., "rule_count": ..., "pair_count": ...,
   "rejected_count": ..., "undecided_count": ..., "unmatched_units": [...],
   "missing_field_finding_count": len(...), "units": units}
  ```
  and each element of `units` (`scripts/server.py:918-930`):
  ```
  {"unit_id": ..., "kind": ..., "paired": [{"rule_id": ..., "reason": ...}, ...],
   "rejected": [{"rule_id": ..., "reason": ...}, ...], "undecided": [...],
   "prior_hit_count": int(...), "prior_check_count": len(...),
   "prior_refused_count": len(...)}
  ```
- A run whose pairing map was never written returns `200` with `documents: []`
  (`scripts/server.py:1203-1204`, `892-901`).
- Status codes: `200`, `404` (malformed or unknown `run_id`).

### `GET /queue`

- Definition: `scripts/server.py:1210`
- Token: required (`scripts/server.py:1210`)
- Accepts: nothing.
- Returns (`scripts/server.py:1217`), quoted:
  ```
  {"jobs": [dict(j) for j in ordered]}
  ```
  where `ordered` is every entry in `JOBS`, sorted by `submitted_at`
  (`scripts/server.py:1216`); each `j` carries the `_STATUS_FIELDS` set (see `/status`
  above).
- Status codes: `200` only.

### `GET /results/{run_id}`

- Definition: `scripts/server.py:1220`
- Token: required (`scripts/server.py:1220`)
- Accepts: path parameter `run_id: str`.
- Behavior (`scripts/server.py:1233-1261`):
  - `run_id` validated against `_RUN_ID_RE` directly (not via `_validated_run_dir`);
    malformed raises `404` (`scripts/server.py:1233-1234`).
  - Unknown `run_id` raises `404` (`scripts/server.py:1237-1238`).
  - `job["status"] != "completed"` raises `400` with
    `detail=f"run not completed (status: {job['status']})"` (`scripts/server.py:1239-1240`).
  - If `deliverables/` exists and is non-empty it is zipped; otherwise the whole run
    folder is zipped; if neither exists, `404` with `detail="no output found for this
    run"` (`scripts/server.py:1242-1247`).
- Returns: a `StreamingResponse` of `media_type="application/zip"`
  (`scripts/server.py:1258-1261`), not JSON, with header
  `Content-Disposition: attachment; filename="{run_id}_deliverables.zip"`.
- Status codes: `200` (zip stream), `400` (not yet completed), `404` (malformed/unknown
  `run_id`, or no output found).

### `GET /console`

- Definition: `scripts/server.py:1267`
- Token: **not required** (no `dependencies=` argument, `scripts/server.py:1267`).
- Accepts: nothing.
- Behavior (`scripts/server.py:1291-1293`): reads `scripts/ui/console.html` from disk
  (`UI_CONSOLE_PATH`, `scripts/server.py:162`) and returns it as `HTMLResponse`; if the
  file is missing, raises `500` with `detail="console.html missing"`.
- Returns: the raw HTML file content, `Content-Type` implied by `HTMLResponse`.
- Status codes: `200`, `500` (console.html missing on disk).
- The route is deliberately not registered at the bare root `"/"`; the docstring at
  `scripts/server.py:1275-1290` records this as a resolved conflict with gate check 94,
  which pins `/status/../..`-style dot-segment traversal behavior at the root path.

### `GET /health`

- Definition: `scripts/server.py:1296`
- Token: **not required** (`scripts/server.py:1296`).
- Accepts: nothing.
- Returns (`scripts/server.py:1307-1309`), quoted:
  ```
  {"status": "ok", "version": app.version,
   "backend_profile": _backend_profile(),
   "default_review_mode": _default_review_mode()}
  ```
  where `app.version` is the literal string `"1.0"` set at `scripts/server.py:330`
  (`FastAPI(title="Project Shimmer front door", version="1.0")`), `_backend_profile()`
  returns `"local"` or `"cloud"` (`scripts/server.py:208-217`), and
  `_default_review_mode()` returns `"paired"` or `"wide"` (`scripts/server.py:220-229`).
- Status codes: `200` only.

### `GET /runs`

- Definition: `scripts/server.py:1312`
- Token: required (`scripts/server.py:1312`)
- Accepts: nothing.
- Returns (`scripts/server.py:1321`), quoted:
  ```
  {"jobs": [dict(j) for j in ordered]}
  ```
  (byte-identical in shape to `GET /queue`, `scripts/server.py:1217`); the docstring at
  `scripts/server.py:1314-1318` states this is deliberate, kept as a separate route
  under the name the console uses.
- Status codes: `200` only.

### `GET /approvals`

- Definition: `scripts/server.py:1355`
- Token: required (`scripts/server.py:1355`)
- Accepts: nothing.
- Returns (`scripts/server.py:1359`), quoted:
  ```
  {"approvals": _pending_approvals()}
  ```
  where each element of the list is built at `scripts/server.py:1346-1351`, quoted:
  ```
  {"run_id": run_dir.name, "topic": record.get("topic"),
   "payload": record.get("payload"), "asked_at": record.get("asked_at")}
  ```
- An empty list is returned when no run has a pending, undecided approval
  (`scripts/server.py:1358`).
- Status codes: `200` only.

### `POST /approvals/{run_id}`

- Definition: `scripts/server.py:1362`
- Token: required (`scripts/server.py:1362`)
- Accepts: path parameter `run_id: str`, and a JSON body (typed `body: dict`,
  `scripts/server.py:1363`) read as:
  - `decision` (required; `400` if empty after stripping, `scripts/server.py:1384-1385`)
  - `rationale` (optional, defaults to `""`, `scripts/server.py:1383`)
- Behavior (`scripts/server.py:1374-1392`):
  - Malformed `run_id` raises `404` (`scripts/server.py:1374-1375`).
  - No `<run>/audit/pending_approval.json` on disk raises `404` with
    `detail="no pending approval for this run_id"` (`scripts/server.py:1379-1380`).
  - Writes `<run>/audit/approval_decision.json` atomically (temp file then replace,
    `scripts/server.py:1390-1392`). The route does not evaluate whether `decision` is a
    recognized value, and does not itself act on the decision
    (`scripts/server.py:1367-1373`).
- Returns (`scripts/server.py:1393`), quoted:
  ```
  {"run_id": run_id, "decision": decision, "rationale": rationale}
  ```
- Status codes: `200`, `404` (malformed `run_id`, or no pending approval for it), `400`
  (`decision` missing/empty).

## Question (a): overlapping or duplicate routes

`GET /queue` (`scripts/server.py:1210-1217`) and `GET /runs` (`scripts/server.py:1312-1321`)
return the identical body shape from the identical source (`JOBS`, sorted by
`submitted_at`): compare the return statements at `scripts/server.py:1217` and
`scripts/server.py:1321`, both `{"jobs": [dict(j) for j in ordered]}` built the same way
(`scripts/server.py:1215-1217` vs. `scripts/server.py:1319-1321`). The docstring at
`scripts/server.py:1314-1318` names this as intentional duplication ("Kept as a separate
route ... because the STEP 6 evidence and acceptance checks name /runs explicitly").

No other route pair returns the same shape from the same data. `GET /findings/{run_id}`
and `GET /pairs/{run_id}` both read from a completed or in-progress run's disk artifacts
but expose disjoint data (Finding records vs. the pairing map; `scripts/server.py:1177-1193`
vs. `1196-1207`).

## Question (b): routes whose output requires calling another route first, and doc status

- `GET /results/{run_id}` requires a prior `run_id`, which only `POST /submit` mints
  (`scripts/server.py:1075`, `_new_run_id()` at `397-402`). This dependency is documented
  in `README.md:1045-1046` ("a `/results` call before the run completes returns 400, so
  poll `/status` first") and in the route's own docstring
  (`scripts/server.py:1226-1227`, "If the run is not completed yet, we return 400 so the
  caller knows to wait").
- `GET /status/{run_id}`, `GET /findings/{run_id}`, `GET /pairs/{run_id}` all require a
  `run_id` from a prior `POST /submit` call; each validates the id format via
  `_RUN_ID_RE` (`scripts/server.py:276`) or `_validated_run_dir`
  (`scripts/server.py:786-798`) and 404s otherwise. This dependency is documented in
  `README.md:897`, `914`, `940` (each example curl call shows `/submit` producing the
  `run_id` used by the later calls) and in `scripts/ui/console.html:217-223` (the
  `submitBtn` handler calls `refreshRuns()` after a successful `/submit`).
- `POST /approvals/{run_id}` requires a `run_id` for a run that has reached a governed
  decision point and requires that `GET /approvals` (or equivalent knowledge) surfaced a
  pending approval first; the route itself 404s with `detail="no pending approval for
  this run_id"` if none exists (`scripts/server.py:1379-1380`). Documented in
  `README.md:963-964` (curl `/approvals` shown before curl `POST /approvals/<run_id>`)
  and in `scripts/ui/console.html:167-201` (`refreshApprovals` populates the table whose
  buttons drive the `POST /approvals/{run_id}` call at `console.html:183-187`).
- `GET /results/{run_id}`'s zip contents are not self-describing as to which document
  produced which file without also having called `/findings` or `/pairs` to get the
  structured breakdown; the docstring at `scripts/server.py:1224-1227` and
  `README.md:956-957` ("Use `/findings` and `/pairs` for a program and `/results` for a
  reader") state this relationship directly.

## Question (c): human-prose vs. machine-structured routes

- `GET /results/{run_id}`: returns a `.zip` of markdown and `.docx` files
  (`scripts/server.py:1220-1261`), explicitly framed in its own docstring as
  "the right thing for a person, the wrong thing for a consumer program"
  (`scripts/server.py:766-767`). Human-prose.
- `GET /console`: returns an HTML page (`scripts/server.py:1267-1293`). Human-facing (a
  browser UI), not machine-structured data.
- `GET /findings/{run_id}` (`scripts/server.py:1177-1193`) and `GET /pairs/{run_id}`
  (`scripts/server.py:1196-1207`): both explicitly built as "the TYPED records instead"
  of prose (`scripts/server.py:766-773`), returning flat JSON objects with an
  `explanation` string field but no rendered prose document.
- `POST /submit`, `GET /status/{run_id}`, `GET /queue`, `GET /runs`, `GET /approvals`,
  `POST /approvals/{run_id}`, `GET /health`: all return flat JSON objects
  (`scripts/server.py:1145-1146`, `1172-1174`, `1217`, `1321`, `1359`, `1393`,
  `1307-1309`). Machine-structured.
- Mixed within one field: `GET /status/{run_id}`'s `error` field
  (`_STATUS_FIELDS`, `scripts/server.py:417`) carries free-form text built from a
  pipeline stdout tail (`scripts/server.py:725`, `f"pipeline exited {proc.returncode}:
  {''.join(tail).strip()[-2000:]}"`), and `GET /findings/{run_id}`'s `explanation` field
  (`scripts/server.py:826`) is documented elsewhere in the codebase (per this file's own
  citations) as "for the human reader."

## Question (d): distinguishing the four run states from responses alone

The states in-progress, finished, governance-blocked, and crashed are read from the
`status` field (`_STATUS_FIELDS`, `scripts/server.py:416-418`), returned by `GET /status/{run_id}`,
`GET /queue`, and `GET /runs`.

- **In-progress**: `status` is `"queued"` (set at `scripts/server.py:1129`, or when a job
  awaits its turn, `scripts/server.py:534-536`) or `"running"` (set at
  `scripts/server.py:537`). While running, `GET /status/{run_id}` also carries a non-null
  `progress` field, the latest `[progress]` line from the pipeline's stdout
  (`_progress_string`, `scripts/server.py:515-521`, applied at `708-714`), and the three
  live counters `pairs_planned`, `pairs_arithmetic_only`, `model_calls`
  (`scripts/server.py:975-999`).
- **Finished (success)**: `status == "completed"`, set via `_status_for_exit_code(0)`
  (`scripts/server.py:305-313`, `_EXIT_STATUS_MAP[0] = "completed"` at
  `scripts/server.py:291`), with `exit_code: 0` and `completed_at` set
  (`scripts/server.py:736-746`).
- **Governance-blocked**: `status` is one of the four values in `GOVERNANCE_STATUSES`
  (`scripts/server.py:301-302`): `"blocked"`, `"stopped_model_approval"`,
  `"stopped_redaction_gate"`, `"refused_sensitivity_layer_inactive"`. These come from
  `_EXIT_STATUS_MAP` (`scripts/server.py:290-298`) for exit codes 5, 3, 4, 6
  respectively. `GOVERNANCE_STATUSES` itself is not exposed as a field in any response;
  a caller distinguishes a governance outcome from a crash only by comparing the
  returned `status` string against this fixed set, which is not returned by any route
  (it exists only in `scripts/server.py:301-302`; the comment at `scripts/server.py:299-301`
  states the console "must render these distinctly from a crash").
  Exit code 5 (`"blocked"`) is documented as ambiguous: it also fires on a draft-mode
  phase-0 generation failure (`scripts/server.py:281-283`, `286-287`), and the code
  comment states "this map cannot distinguish the two by exit code alone, so the console
  note tells the operator to check the log tail" (`scripts/server.py:283-285`).
- **Crashed**: `status == "failed"`, the fallback in `_status_for_exit_code` for any
  exit code not in `_EXIT_STATUS_MAP` (`scripts/server.py:312-313`), or set directly when
  `exit_code is None` (a run timeout, `scripts/server.py:739-740`, `719-721`). The
  `error` field is populated with detail (`scripts/server.py:725` for a non-zero exit,
  `scripts/server.py:720` for a timeout, `scripts/server.py:727` for an exception during
  the subprocess plumbing).
  Two additional terminal statuses exist outside all four categories named in the
  question: `"snapshot_conflict"` (exit code 2, `--save-snapshot` conflicts,
  `scripts/server.py:292`) and `"operator_abort"` (exit code 7, meta-signature decline,
  `scripts/server.py:297`), neither in `GOVERNANCE_STATUSES` nor treated as `"failed"`.
  `"interrupted"` is a further status, set only by `_rebuild_jobs_from_disk` at server
  restart for a job that was `"running"` when the process died
  (`scripts/server.py:471-476`), with `error` defaulted to `"server restarted while this
  run was in progress"` (`scripts/server.py:473`).
- No route returns a field named `state` or a boolean grouping these four categories;
  a caller determines the category by string-matching `status` itself, as
  `scripts/ui/console.html:135-141` does (`statusClass`, checking `status === 'completed'`,
  then membership in a 4-element governance array, then membership in a 3-element
  `['failed', 'snapshot_conflict', 'operator_abort']` array, else a neutral default that
  also covers `"queued"`, `"running"`, and `"interrupted"`).

## Question (e): what `scripts/ui/console.html` calls, route by route

- `GET /runs`: called by `refreshRuns()` (`console.html:143-165`), on click of
  `refreshRunsBtn` (`console.html:203`) and after a successful `/submit`
  (`console.html:223`). Reads `data.jobs || data.runs` (`console.html:149`): the code
  tolerates either key name, though the live route only ever returns `jobs`
  (`scripts/server.py:1321`). Per job it reads `j.run_id`, `j.task`, `j.status`,
  `j.submitted_at`, `j.exit_code`, `j.error` (`console.html:154-159`), all present in
  `_STATUS_FIELDS` (`scripts/server.py:416-418`). It also constructs
  `j.run_id + '/logs/pipeline_stdout.log'` as a display-only path string
  (`console.html:152`); this path is never fetched by the page (there is no download
  route for it, stated in `console.html:96-98`) and `logs_path` is not a field returned
  by any route (not in `_STATUS_FIELDS`, `scripts/server.py:416-418`), the console
  constructs it itself from `run_id` and a hardcoded relative path, something not
  present anywhere in the API surface.
- `GET /approvals`: called by `refreshApprovals()` (`console.html:167-201`), on click of
  `refreshApprovalsBtn` (`console.html:204`) and after a decision is submitted
  (`console.html:187`). Reads `data.approvals` (`console.html:173`), and per entry `a.run_id`,
  `a.topic`, `a.asked_at` (`console.html:193-195`), all present in the route's own
  return shape (`scripts/server.py:1346-1351`); `a.payload` is fetched by the route but
  never read by the console.
- `POST /approvals/{run_id}`: called by the APPROVE/DENY button handlers
  (`console.html:180-189`), sending `{decision, rationale: 'decided via console'}`
  (`console.html:186`). `rationale` is always the literal string `'decided via console'`;
  the console provides no field for the operator to enter a custom rationale even though
  the route accepts an arbitrary string (`scripts/server.py:1383`).
- `POST /submit`: called by the `submitBtn` handler (`console.html:206-230`), sending
  `task`, `question` (only if non-empty, `console.html:213`), `sensitive` (always sent,
  `'true'`/`'false'` string, `console.html:214`), and `files` (`console.html:215`). The
  console never sends the `review_mode` field that the route accepts
  (`scripts/server.py:1010`, `1052-1059`); a submission from the console always gets the
  server's default review mode (`_default_review_mode()`, `scripts/server.py:220-229`).
- Not called by the console at all: `GET /status/{run_id}`, `GET /findings/{run_id}`,
  `GET /pairs/{run_id}`, `GET /queue`, `GET /results/{run_id}`, `GET /health`. (`GET /console`
  is the page's own retrieval route and is not fetched from within the page.)
- Nothing in `console.html` calls or references any URL, path, or data shape absent from
  the 11-route API surface, apart from the display-only log-path string noted above,
  which is constructed client-side and never fetched.

## Question (f): every environment variable the server reads, its default, and what breaks if missing

All are read at module import/startup unless noted; the full reference table is also at
`scripts/server.py:46-93` and `README.md:1055-1072`.

| Variable | Default if unset | Read at | What breaks if missing |
|---|---|---|---|
| `SHIMMER_TOKEN_HASH` | none (required) | `scripts/server.py:347` (`_check_token`, every request) and `scripts/server.py:1411` (startup check) | If unset, `python scripts/server.py` prints a refusal message and calls `sys.exit(1)` (`scripts/server.py:1411-1422`) before `uvicorn.run` is ever reached. If the module is imported without going through `__main__` (e.g. `uvicorn scripts.server:app`), `_check_token` instead raises `401` with `detail="server has no token configured"` on every request (`scripts/server.py:347-350`). |
| `SHIMMER_MODE` | `"integrated"` | `scripts/server.py:189` | Passed as `--mode` to the pipeline subprocess (`scripts/server.py:640`); with the default, the corpus-ingest promotion-exclusion hook is active (`scripts/server.py:55-57`). Missing just means the default `"integrated"` behavior. |
| `SHIMMER_TASK` | `"review"` | `scripts/server.py:190` | Used as the fallback for `/submit`'s `task` form field when omitted (`scripts/server.py:1048`). Missing means `/submit` calls with no `task` field default to `"review"`. |
| `SHIMMER_SENSITIVE` | `False` | `scripts/server.py:191` (`_env_bool`) | Used as the fallback for `/submit`'s `sensitive` form field when omitted (`scripts/server.py:1045-1046`). Missing means a submission with no `sensitive` field is treated as non-sensitive, and the run is launched with `--sensitivity-layer-inactive-override --no-redaction-override` (`scripts/server.py:659-660`). |
| `SHIMMER_MAX_DOCS` | `4` | `scripts/server.py:192` (`_env_int`) | Passed as `--max-concurrent-docs` (`scripts/server.py:642`). Missing means 4. |
| `SHIMMER_PORT` | `8000` | `scripts/server.py:193` | Passed to `uvicorn.run(..., port=PORT, ...)` (`scripts/server.py:1442`), only reached under `__main__`. Missing means port 8000. |
| `SHIMMER_HOST` | `"0.0.0.0"` | `scripts/server.py:194` | Passed to `uvicorn.run(..., host=HOST, ...)` (`scripts/server.py:1442`). Missing means bind to all interfaces. |
| `SHIMMER_AUTO_CLEAR` | `True` | `scripts/server.py:195` (`_env_bool`) | Controls whether `_auto_clear()`/`_clear_system_draft()` run after each job (`scripts/server.py:750-752`). Missing means ingested files are cleared after every run. |
| `SHIMMER_OUTPUT_DIR` | `ROOT / "output" / "runs"` | `scripts/server.py:198` | Sets `RUNS_DIR`, the root every run folder, `_status_path`, `_rebuild_jobs_from_disk`, and `/results` are built under (`scripts/server.py:198`, used throughout, e.g. `421-426`, `458`, `588`, `1242`). Missing means the default `output/runs/` under the repo root. |
| `SHIMMER_LOG_LEVEL` | `"info"` | `scripts/server.py:196` | Passed to `uvicorn.run(..., log_level=LOG_LEVEL)` (`scripts/server.py:1442`). Missing means `"info"`. |
| `SHIMMER_RUN_TIMEOUT_S` | `0` | `scripts/server.py:200` (`_env_int`) | Used by `_effective_run_timeout()` when the backend profile is not `"local"` (`scripts/server.py:232-237`). `0` means no `threading.Timer` is armed at all (`scripts/server.py:684`), i.e. unbounded run time. Missing means unbounded. |
| `SHIMMER_LOCAL_RUN_TIMEOUT_S` | `7200` | `scripts/server.py:201` | Used by `_effective_run_timeout()` when `SHIMMER_BACKEND_PROFILE == "local"` (`scripts/server.py:235-236`). Missing means 7200 seconds (2 hours) under local mode. |
| `SHIMMER_BACKEND_PROFILE` | unset (treated as cloud) | `scripts/server.py:217` (`_backend_profile`), `235`, `244`, `656-658` | Read live (not cached) in several places. Anything other than the exact string `"local"` is treated as the cloud profile (`scripts/server.py:217`). Missing means cloud profile: `_default_review_mode()` returns `"wide"` (`scripts/server.py:229`), `_effective_run_timeout()` uses `SHIMMER_RUN_TIMEOUT_S` not `SHIMMER_LOCAL_RUN_TIMEOUT_S` (`scripts/server.py:236-237`), `check_local_model_availability()` short-circuits to `(True, "not in local mode")` (`scripts/server.py:244-245`), and no `--backend-profile` flag is appended to the pipeline subprocess argv (`scripts/server.py:656-658`). |
| `SHIMMER_PROVIDER_TIMEOUT_S` | `600` | not read by `scripts/server.py` itself; read by the pipeline subprocess (`agent_wrapper.py`, per `scripts/server.py:84-86`) | Nothing breaks in the server process; this variable only affects the pipeline subprocess it launches. |
| `SHIMMER_MAX_UPLOAD_MB` | `25` | `scripts/server.py:268` | Enforced per-file in `/submit` (`scripts/server.py:1080`, `1084-1089`). Missing means a 25 MB per-file cap. |
| `SHIMMER_MAX_UPLOAD_TOTAL_MB` | `200` | `scripts/server.py:269` | Enforced across the whole submission in `/submit` (`scripts/server.py:1081`, `1091-1096`). Missing means a 200 MB total cap. |
| `SHIMMER_MAX_UPLOAD_FILES` | `50` | `scripts/server.py:270` | Enforced as a file-count cap in `/submit` (`scripts/server.py:1070-1073`). Missing means a 50-file cap. |
| `SHIMMER_APPROVAL_WAIT_S` | `3600` | not read by `scripts/server.py` itself; read by the pipeline subprocess's `--operator-channel file` handler, per `scripts/server.py:90-93` | Nothing breaks in the server process; this variable only affects how long the pipeline subprocess waits for a decision file before defaulting to `DEFERRED`. |

`_config_summary()` (`scripts/server.py:316-323`) prints every one of the server-process-local
resolved values (all rows above except `SHIMMER_PROVIDER_TIMEOUT_S` and
`SHIMMER_APPROVAL_WAIT_S`, which are pipeline-subprocess-only) to stderr once at startup
(`scripts/server.py:1436`), reached only under `__main__`.

## Functionality a caller cannot currently do

- **List only past (terminal-state) runs, or filter/paginate the run list.** `GET /queue`
  and `GET /runs` both return every job unconditionally, oldest-first
  (`scripts/server.py:1210-1217`, `1312-1321`); there is no query parameter, filter, or
  pagination on either route, and no route restricts the list to a status subset.
- **Cancel or stop a running or queued job.** There is no route that accepts a `run_id`
  and terminates or dequeues it. `_run_job`'s subprocess is only ever terminated by the
  internal `SHIMMER_RUN_TIMEOUT_S`/`SHIMMER_LOCAL_RUN_TIMEOUT_S` timer
  (`scripts/server.py:673-694`), which is not caller-triggerable.
- **Download a single deliverable file rather than the whole archive.** `GET
  /results/{run_id}` always returns a zip of the entire deliverables tree (or the whole
  run tree as a fallback) built in memory (`scripts/server.py:1249-1261`); there is no
  route parameterized by a file path within a run's output.
- **Learn, from a route, why a run refused to start or was rejected, beyond the `POST
  /submit` response itself.** A rejected submission gets its reason synchronously in the
  `400` response body at submit time (`scripts/server.py:1057-1122`); once a job is
  queued, no route surfaces a separate list of "would-be rejections": a run that is
  accepted but later stops for a governance reason is visible only via its terminal
  `status` string and `error` field on `GET /status/{run_id}` (see Question d).
- **Delete a run's output, or a queued/terminal job record.** No route removes a run
  folder, a `status.json`, or an entry from `JOBS`; the only removal logic
  (`_auto_clear`, `scripts/server.py:545-572`) operates on `input/context/`, not on run
  output or job records.
- **Retrieve the run's log file (`pipeline_stdout.log`) over HTTP.** The console
  constructs its path as a display string (`console.html:152`) but states directly
  ("there is no download route for it", `console.html:96-98`) that it must be opened on
  the machine running the server; no route in `scripts/server.py` serves this file.
- **Re-run, retry, or clone a prior submission.** `POST /submit` always requires the
  caller to resupply `files`/`task`/`question` from scratch (`scripts/server.py:1005-1146`);
  no route accepts an existing `run_id` and starts a new job from its stored inputs.
- **Discover, from any response, which of the 11 routes exist or what they accept**,
  other than by reading source or documentation: `scripts/server.py` registers no
  OpenAPI/docs-disabling override, but no route in the inventory above returns a
  machine-readable list of the API's own routes (the FastAPI-generated `/openapi.json`
  and `/docs` are not among the 11 hand-authored routes catalogued here, and this
  inventory makes no claim about whether FastAPI's own auto-generated schema routes are
  reachable).
- **See a token's remaining validity, rotate a token, or manage multiple tokens.**
  `_check_token` (`scripts/server.py:339-359`) compares against exactly one
  `SHIMMER_TOKEN_HASH` value read once at process start; there is no route to issue,
  revoke, inspect, or rotate a token.
